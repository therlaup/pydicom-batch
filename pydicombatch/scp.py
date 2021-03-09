import os
import sys
import uuid
from .common import setup_logging

from queue import Queue
from threading import Thread

from pydicom.dataset import Dataset

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

APP_LOGGER = setup_logging(app_name='scp')
APP_LOGGER.debug(f'pydicombatch storage server')




# def handle_store(event, config, app_logger):
#     """Handle a C-STORE request.
#     Parameters
#     ----------
#     event : pynetdicom.event.event
#         The event corresponding to a C-STORE request.
#     config : 
#         config data
#     app_logger : logging.Logger
#         The application's logger.
#     Returns
#     -------
#     status : pynetdicom.sop_class.Status or int
#         A valid return status code, see PS3.4 Annex B.2.3 or the
#         ``StorageServiceClass`` implementation for the available statuses
#     """

#     try:
#         ds = event.dataset
#         # Remove any Group 0x0002 elements that may have been included
#         ds = ds[0x00030000:]
#     except Exception as exc:
#         app_logger.error("Unable to decode the dataset")
#         app_logger.exception(exc)
#         # Unable to decode dataset
#         return 0x210

#     # Add the file meta information elements
#     ds.file_meta = event.file_meta

#     # Because pydicom uses deferred reads for its decoding, decoding errors
#     #   are hidden until encountered by accessing a faulty element
#     try:
#         sop_class = ds.SOPClassUID
#         sop_instance = ds.SOPInstanceUID
#     except Exception as exc:
#         app_logger.error(
#             "Unable to decode the received dataset or missing 'SOP Class "
#             "UID' and/or 'SOP Instance UID' elements"
#         )
#         app_logger.exception(exc)
#         # Unable to decode dataset
#         return 0xC210

#     try:
#         # Get the elements we need
#         mode_prefix = SOP_CLASS_PREFIXES[sop_class][0]
#     except KeyError:
#         mode_prefix = 'UN'

#     filename = f'{mode_prefix}.{sop_instance}'
#     app_logger.info(f'Storing DICOM file: {filename}')    

#     status_ds = Dataset()
#     status_ds.Status = 0x0000

#     # Try to save to output-directory
#     if config['output']['directory'] is not None:
#         filename = os.path.join(config['output']['directory'], filename)
#         try:
#             os.makedirs(config['output']['directory'], exist_ok=True)
#         except Exception as exc:
#             app_logger.error('Unable to create the output directory:')
#             app_logger.error(f"    {config['output']['directory']}")
#             app_logger.exception(exc)
#             # Failed - Out of Resources - IOError
#             status_ds.Status = 0xA700
#             return status_ds

#     if os.path.exists(filename):
#         app_logger.warning('DICOM file already exists, overwriting')        
        
#     try:
#         if event.context.transfer_syntax == DeflatedExplicitVRLittleEndian:
#             # Workaround for pydicom issue #1086
#             with open(filename, 'wb') as f:
#                 f.write(b'\x00' * 128)
#                 f.write(b'DICM')
#                 f.write(write_file_meta_info(f, event.file_meta))
#                 f.write(encode(ds, False, True, True))
#         else:
#             # We use `write_like_original=False` to ensure that a compliant
#             #   File Meta Information Header is written
#             ds.save_as(filename, write_like_original=False)

#         status_ds.Status = 0x0000  # Success
#     except IOError as exc:
#         app_logger.error('Could not write file to specified directory:')
#         app_logger.error(f"    {os.path.dirname(filename)}")
#         app_logger.exception(exc)
#         # Failed - Out of Resources - IOError
#         status_ds.Status = 0xA700
#     except Exception as exc:
#         app_logger.error('Could not write file to specified directory:')
#         app_logger.error(f"    {os.path.dirname(filename)}")
#         app_logger.exception(exc)
#         # Failed - Out of Resources - Miscellaneous error
#         status_ds.Status = 0xA701

#     return status_ds


# def start_server(ae, config):

    
#     transfer_syntax = ALL_TRANSFER_SYNTAXES[:]
#     store_handlers = [(evt.EVT_C_STORE, handle_store, [config, APP_LOGGER])]
#     ae.ae_title = config['local']['aet']
#     for cx in AllStoragePresentationContexts:
#         ae.add_supported_context(cx.abstract_syntax, transfer_syntax)

#     scp = ae.start_server(
#         ('', config['local']['port']), block=False, evt_handlers=store_handlers
#         )
#     return scp


class SCP(object):
    """ SCP class
    This class is used to run a local SCP (server) that handles DIMSE requests (c-store, c-echo)
    """

    def __init__(self, config):
        self.config = config
        self.ae = self.create_ae() 
        self.scp = None
        # self.anon_queue = Queue()
        # self.start_anon_workers()
        
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
    
    # def anon_cmd(file):
    #     return 'java -jar ./DicomAnonymizerTool/DAT.jar -da {anon_script} -lut {anon_lut} -in {file} -out {file}'.format(
    #         file = file, 
    #         anon_script = self.config['output']['anonymization_script'],
    #         anon_lut = self.config['output']['anonymization_lookup_table'])

    # def anonymize_file(i, q):
    #     while True:
    #         filename = q.get()
    #         os.system(self.anon_cmd(filename))
    #         q.task_done()

    # def start_anon_workers():
    #     self.anon_workers = []
    #     for i in range(num_fetch_threads):
    #         worker = Thread(target=self.anonymize_file, args=(i,self.anon_queue,))
    #         worker.setDaemon(True)
    #         worker.start()
    #         self.anon_workers.append(worker)

    def start_server(self):
        print('Starting server')
        handlers = [(evt.EVT_C_STORE, self.handle_store), (evt.EVT_C_ECHO, self.handle_echo)]
        self.scp = self.ae.start_server(('', self.config['local']['port']), block=False, evt_handlers=handlers)

    def stop_server(self):
        print('Stopping server')
        self.scp.shutdown()

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

        filename = os.path.join(self.config['output']['directory'],'{0!s}.dcm'.format(uuid.uuid4()))

        APP_LOGGER.info('Storing DICOM file: {0!s}'.format(filename))

        if os.path.exists(filename):
            APP_LOGGER.warning('DICOM file already exists, overwriting')

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

            status_ds.Status = 0x0000 # Success
        except IOError:
            APP_LOGGER.error('Could not write file to specified directory:')
            APP_LOGGER.error("    {0!s}".format(os.path.dirname(filename)))
            APP_LOGGER.error('Directory may not exist or you may not have write '
                        'permission')
            # Failed - Out of Resources - IOError
            status_ds.Status = 0xA700
        except:
            APP_LOGGER.error('Could not write file to specified path:')
            APP_LOGGER.error("    {0!s}".format(filename))
            # Failed - Out of Resources - Miscellaneous error
            status_ds.Status = 0xA701


        return status_ds