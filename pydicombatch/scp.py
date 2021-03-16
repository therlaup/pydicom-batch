import os
import sys
import uuid
import time
from queue import Queue
from threading import Thread
import tqdm
from pydicom import dcmread
from pydicom.dataset import Dataset
from pynetdicom.apps.common import ElementPath
import inquirer
import shutil

from pydicom.uid import (
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    ExplicitVRBigEndian,
    DeflatedExplicitVRLittleEndian,
    PILSupportedCompressedPixelTransferSyntaxes,
    JPEGLossless
)

from pynetdicom import (
    AE, evt, QueryRetrievePresentationContexts, AllStoragePresentationContexts
)
from pynetdicom.apps.common import create_dataset
from pynetdicom._globals import ALL_TRANSFER_SYNTAXES, DEFAULT_MAX_LENGTH
from pynetdicom.pdu_primitives import SOPClassExtendedNegotiation
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelMove,
    PatientStudyOnlyQueryRetrieveInformationModelMove,
    ModalityWorklistInformationFind,
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind,
    PatientStudyOnlyQueryRetrieveInformationModelFind
)


class SCP(object):
    """ SCP class
    This class is used to run a local SCP (server) that handles DIMSE requests (c-store, c-echo)
    """

    def __init__(self, config):
        self.config = config
        self.anonymization_enabled = self.check_anon_engine()
        self.ae = self.create_ae() 
        self.scp = None
        self.writing_queue = Queue()
        self.start_file_writing_workers()
        self.file_count = 0
        self.time_start =  time.time()

    def check_anon_engine(self):
        """
        Return True if anonymization is enabled and script / look up table file exist
        """
        if (self.config['anonymization'] and self.config['anonymization']['enabled']):
            # Anonymization enabled
            # Ensure that RSNA DICOM Anonymizer is found
            if not os.path.isfile('./DicomAnonymizerTool/DAT.jar'):
                questions = [
                inquirer.List('anon_files',
                                message="RSNA DICOM Anonymizer JAR file not found. Do you still want to proceed?",
                                choices=['Continue without anonymization', 'Exit'],
                            ),
                ]
                answers = inquirer.prompt(questions)
                if answers['anon_files'] == 'Exit':
                    sys.exit()
                else:
                    print('Anonymization DISABLED')
                    return False

            # Ensure that anonymization scripts are found
            anon_script = self.config['anonymization']['script']
            anon_lut = self.config['anonymization']['lookup_table']
            if not os.path.isfile(anon_script):
                questions = [
                inquirer.List('anon_files',
                                message="Anonymization script not found. Do you still want to proceed?",
                                choices=['Continue without anonymization', 'Exit'],
                            ),
                ]
                answers = inquirer.prompt(questions)
                if answers['anon_files'] == 'Exit':
                    sys.exit()
                else:
                    print('Anonymization DISABLED')
                    return False
            
            if not os.path.isfile(anon_lut):
                questions = [
                inquirer.List('anon_files',
                                message="Anonymization look up table not found. Do you still want to proceed?",
                                choices=['Continue without look up table', 'Exit'],
                            ),
                ]
                answers = inquirer.prompt(questions)
                if answers['anon_files'] == 'Exit':
                    sys.exit()

            print('Anonymization ENABLED')    
            return True
        else:
            print('Anonymization DISABLED')
            return False


    def create_ae(self):
        # Create application entity
        ae = AE(ae_title=self.config['local']['aet'])

        # Set timeouts
        ae.acse_timeout = 300
        ae.dimse_timeout = 300
        ae.network_timeout = 300
        ae.maximum_pdu_size = 16384

        transfer_syntax = [ImplicitVRLittleEndian,
                        ExplicitVRLittleEndian,
                        DeflatedExplicitVRLittleEndian,
                        ExplicitVRBigEndian]
        transfer_syntax += PILSupportedCompressedPixelTransferSyntaxes

        for cx in AllStoragePresentationContexts:
            ae.add_supported_context(cx.abstract_syntax, transfer_syntax)

        return ae
    
    def anon_cmd(self, file):
        return 'cd ./DicomAnonymizerTool && java -jar DAT.jar -da {anon_script} -lut {anon_lut} -in {file} -out {file}  >/dev/null 2>&1'.format(
            file = file, 
            anon_script = self.config['anonymization']['script'],
            anon_lut = self.config['anonymization']['lookup_table'])

    def write_file(self, i, q):
        while True:
            tmp_filename, tmp_ds = q.get()
            # Anonymize file if enabled
            if self.anonymization_enabled:
                os.system(self.anon_cmd(tmp_filename))
                ds = dcmread(tmp_filename)
            else:
                ds = tmp_ds
            # Apply decompression if enabled
            if self.config['output']['decompress']:
                ds.decompress()
                ds.save_as(tmp_filename, write_like_original=False)
            # Move file to desired directory_structure 
            dir_structure = self.config['output']['directory_structure'].split('/')
            dir_structure = [str(ds[ElementPath(x).tag].value) for x in dir_structure if x]
            filename = str(ds[ElementPath(self.config['output']['filename']).tag].value) + '.dcm'
            filedir = os.path.join(self.config['output']['directory'], *dir_structure)
            filepath = os.path.join(filedir, filename)
            os.makedirs(filedir, exist_ok = True)
            shutil.move(tmp_filename, filepath)
            q.task_done()

    def start_file_writing_workers(self):
        self.file_writing_workers = []
        for i in range(self.config['request']['threads']):
            worker = Thread(target=self.write_file, args=(i,self.writing_queue,))
            worker.setDaemon(True)
            worker.start()
            self.file_writing_workers.append(worker)

    def start_server(self):
        print('Starting local storage SCP server on port {}'.format(self.config['local']['port']))
        # Create a temporary directory to store files prior to anonymization
        temp_dir = os.path.join(self.config['output']['directory'],'tmp')
        os.makedirs(temp_dir, exist_ok = True)
        handlers = [(evt.EVT_C_STORE, self.handle_store), (evt.EVT_C_ECHO, self.handle_echo)]
        self.scp = self.ae.start_server(('', self.config['local']['port']), block=False, evt_handlers=handlers)

    def stop_server(self):
        old_qsize = self.writing_queue.qsize()
        pbar = tqdm.tqdm(total=old_qsize, 
            desc='Post-processing ', 
            unit='files')
        while self.writing_queue.qsize():
            qsize = self.writing_queue.qsize()
            pbar.update(old_qsize-qsize)
            old_qsize = qsize
            time.sleep(0.1)
        pbar.update(old_qsize-self.writing_queue.qsize())
        pbar.close()    
        self.writing_queue.join()
        time_elapsed = time. time() - self.time_start
        print('Stopping local storage SCP server: {} files transferred in {:.1f} seconds ({:.2f} files/s)'.format(self.file_count, time_elapsed, self.file_count/time_elapsed))
        self.scp.shutdown()
        temp_dir = os.path.join(self.config['output']['directory'],'tmp')
        # Remove temporary directory if empty
        if not os.listdir(temp_dir):
            shutil.rmtree(temp_dir)


    def handle_echo(self, event):
        """Respond to a C-ECHO service request.
        
            The status returned to the peer AE in the C-ECHO response. Must be
            a valid C-ECHO status value for the applicable Service Class as
            either an ``int`` or a ``Dataset`` object containing (at a
            minimum) a (0000,0900) *Status* element.
        """
        print('Echo received')
        return 0x0000

    def handle_store(self, event):
        """Handle a C-STORE request.

        Parameters
        ----------
        event : pynetdicom.event.event
            The event corresponding to a C-STORE request. Attributes are:

            * *assoc*: the ``association.Association`` instance that received the
            request
            * *context*: the presentation context used for the request's *Data
            Set* as a ``namedtuple``
            * *request*: the C-STORE request as a ``dimse_primitives.C_STORE``
            instance

            Properties are:

            * *dataset*: the C-STORE request's decoded *Data Set* as a pydicom
            ``Dataset``

        Returns
        -------
        status : pynetdicom.sop_class.Status or int
            A valid return status code, see PS3.4 Annex B.2.3 or the
            ``StorageServiceClass`` implementation for the available statuses
        """

        
        mode_prefixes = {'CT Image Storage' : 'CT',
            'Enhanced CT Image Storage' : 'CTE',
            'MR Image Storage' : 'MR',
            'Enhanced MR Image Storage' : 'MRE',
            'Positron Emission Tomography Image Storage' : 'PT',
            'RT Plan Storage' : 'RP',
            'RT Structure Set Storage' : 'RS',
            'Computed Radiography Image Storage' : 'CR',
            'Ultrasound Image Storage' : 'US',
            'Enhanced Ultrasound Image Storage' : 'USE',
            'X-Ray Angiographic Image Storage' : 'XA',
            'Enhanced XA Image Storage' : 'XAE',
            'Nuclear Medicine Image Storage' : 'NM',
            'Secondary Capture Image Storage' : 'SC'
        }

        ds = event.dataset
        # Because pydicom uses deferred reads for its decoding, decoding errors
        #   are hidden until encountered by accessing a faulty element
        try:
            sop_class = ds.SOPClassUID
            sop_instance = ds.SOPInstanceUID
        except Exception as exc:
            # Unable to decode dataset
            return 0xC210

        try:
            # Get the elements we need
            mode_prefix = mode_prefixes[sop_class.name]
        except KeyError:
            mode_prefix = 'UN'

        filename = os.path.join(self.config['output']['directory'],'tmp/{0!s}.dcm'.format(uuid.uuid4()))

        # Presentation context
        cx = event.context

        meta = Dataset()
        meta.MediaStorageSOPClassUID = sop_class
        meta.MediaStorageSOPInstanceUID = sop_instance
        
        meta.TransferSyntaxUID = cx.transfer_syntax
        

        ds.file_meta = meta
        ds.is_little_endian = cx.transfer_syntax.is_little_endian
        ds.is_implicit_VR = cx.transfer_syntax.is_implicit_VR

        status_ds = Dataset()
        
        try:
            ds.save_as(filename, write_like_original=False)
            self.file_count += 1
            self.writing_queue.put((filename, ds))
            status_ds.Status = 0x0000 # Success
        except IOError:
            # Failed - Out of Resources - IOError
            status_ds.Status = 0xA700
        except:
            # Failed - Out of Resources - Miscellaneous error
            status_ds.Status = 0xA701


        return status_ds