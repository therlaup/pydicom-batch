from pynetdicom import AE
from pynetdicom.sop_class import VerificationSOPClass
from pynetdicom.apps.common import ElementPath
from pydicom.dataset import Dataset
from .common import setup_logging
import os.path
import csv
import time
import tqdm
import concurrent.futures
import numpy as np

from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian,
    generate_uid
)

from pynetdicom import (
    AE, QueryRetrievePresentationContexts,
    BasicWorklistManagementPresentationContexts,
    PYNETDICOM_UID_PREFIX,
    PYNETDICOM_IMPLEMENTATION_UID,
    PYNETDICOM_IMPLEMENTATION_VERSION
)

from pynetdicom._globals import DEFAULT_MAX_LENGTH
from pynetdicom.pdu_primitives import SOPClassExtendedNegotiation
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind,
    PatientStudyOnlyQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelMove,
    PatientStudyOnlyQueryRetrieveInformationModelMove
)

APP_LOGGER = setup_logging('scu')
APP_LOGGER.debug(f'pydicombatch scu')

def dataset_to_csv(ds, filepath, fieldnames):
    write_dict = {}
    for key in fieldnames:
        write_dict[key] = str(ds[key].value)

    if os.path.exists(filepath):
        with open(filepath, 'a', newline='', ) as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, dialect='excel')
            writer.writerow(write_dict)
    else:
        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, dialect='excel')
            writer.writeheader()
            writer.writerow(write_dict)

def add_element_to_list(element_list, key, value):
    if [x if ((x.partition('=')[0] == key) or (x == key)) else None for x in element_list]:
        return [f'{key}={value}' if ((x.partition('=')[0] == key) or (x == key)) else x for x in element_list]
    else:
        element_list.append(f'{key}={value}')
        return element_list

def create_dataset(request):
    ds = Dataset()
    try:
        elements = [ElementPath(path) for path in request['elements']]
        for elem in elements:
            ds = elem.update(ds)
    except Exception as exc:
        if APP_LOGGER:
            APP_LOGGER.error(
                'Exception raised trying to parse the supplied keywords'
            )
        raise exc
    return ds

def create_requests(request):
    requests = []
    if request['elements_batch_file']:
        if os.path.exists(request['elements_batch_file']):
            with open(request['elements_batch_file'], newline='') as csvfile:
                reader = csv.DictReader(csvfile, dialect='excel')
                for row in reader:
                    row_request = request.copy()
                    for key in row:
                        row_request['elements'] = add_element_to_list(row_request['elements'], key, row[key])
                    requests.append(row_request)
        else:
            requests.append(request)
    else:
        requests.append(request)
    return requests

def thread_scu_function(config, pbar, requests):
    scu = SCU(config)
    scu.pbar = pbar
    scu.process_requests_batch(list(requests))
    return

def process_request_batch(config):
    requests = create_requests(config['request'])
    split_requests = np.array_split(requests, config['request']['threads'])
    pbar = tqdm.tqdm(total=len(requests), 
        desc='Sending {} requests '.format(config['request']['type']), 
        unit='rqst')
    fn = lambda x : thread_scu_function(config, pbar, x)
    with concurrent.futures.ThreadPoolExecutor(max_workers=config['request']['threads']) as executor:
        executor.map(fn, split_requests)    


class SCU(object):
    """ SCU class
    This class is used to send batches of DIMSE requests (c-find, c-echo, c-move) to a remote SCP
    """
    def __init__(self, config):
        self.config = config
        self.ae = self.create_ae()
        self.query_model = self.create_query_model()
        self.pbar = None
        
    def create_ae(self):
        # Create application entity
        ae = AE(ae_title=self.config['local']['aet'])

        # Set timeouts
        ae.acse_timeout = 300
        ae.dimse_timeout = 300
        ae.network_timeout = 300

        # Set the Presentation Contexts we are requesting the Find SCP support
        if self.config['request']['type'].lower() == 'c-find':
            ae.requested_contexts = QueryRetrievePresentationContexts
                
        elif self.config['request']['type'].lower() == 'c-echo':
            ae.requested_contexts = [VerificationSOPClass]

        elif self.config['request']['type'].lower() == 'c-move':
            ae.requested_contexts = QueryRetrievePresentationContexts

        return ae

    def establish_association(self):
        return self.ae.associate(self.config['pacs']['hostname'], 
            self.config['pacs']['port'],  
            ae_title=self.config['pacs']['aet'],
            max_pdu=16382)

    def retry_association(self):

        for i in range(100):
            if not self.association.is_established:
                time.sleep(1)
                self.association = self.establish_association()
            else:
                return
        
        sys.exit(1)


    def create_query_model(self):
        request = self.config['request']
        query_model = None
        if request['type'].lower() == 'c-find':
            if request['model'] == 'study':
                query_model = StudyRootQueryRetrieveInformationModelFind
            elif self.config['request']['model'] == 'psonly':
                query_model = PatientStudyOnlyQueryRetrieveInformationModelFind
            else:
                query_model = PatientRootQueryRetrieveInformationModelFind
        elif request['type'].lower() == 'c-move':
            if request['model'] == 'study':
                query_model = StudyRootQueryRetrieveInformationModelMove
            elif self.config['request']['model'] == 'psonly':
                query_model = PatientStudyOnlyQueryRetrieveInformationModelMove
            else:
                query_model = PatientRootQueryRetrieveInformationModelMove
        return query_model

    def process_requests_batch(self, requests):
        self.association = self.establish_association()
        for request in requests:
            self.process_request(request)
            time.sleep(request['throttle_time'])
        self.association.release()
        
    
    def process_request(self, request):
        if request['type'].lower() == 'c-find':
            self.send_find(request)
        if request['type'].lower() == 'c-move':
            self.send_move(request)
    
    
    # def send_batch_find(self, request):
    #     if (os.path.exists(request['elements_batch_file'])):
    #         with open(request['elements_batch_file'], newline='') as csvfile:
    #             reader = csv.DictReader(csvfile, dialect='excel')
    #             for row in tqdm(list(reader), unit='request'):
    #                 time.sleep(request['throttle_time'])
    #                 row_request = request.copy()

    #                 for key in row:
    #                     row_request['elements'] = add_element_to_list(row_request['elements'], key, row[key])
                                        
    #                 self.send_find(row_request)
    #     else:
    #         print('Supplied elements_batch_file does not exist: ', request['elements_batch_file'])

    def send_find(self, request):
        
        identifier = create_dataset(request)
    
        keywords = [ElementPath(path).keyword for path in request['elements']]

        if not self.association.is_established:
            self.retry_association()
        
        if self.association.is_established:
            responses = self.association.send_c_find(identifier, self.query_model)
                    
            for (status, rsp_identifier) in responses:

                if status and status.Status in [0xFF00, 0xFF01]:
                    path = os.path.join(self.config['output']['directory'], self.config['output']['database_file'])
                    dataset_to_csv(rsp_identifier, path, keywords)
                elif status and status.Status in [0x0000]:
                    if self.pbar:
                        self.pbar.update(1)



    def send_move(self, request):
        
        identifier = create_dataset(request)
    
        keywords = [ElementPath(path).keyword for path in request['elements']]

        if not self.association.is_established:
            self.retry_association()
        
        if self.association.is_established:
            responses = self.association.send_c_move(identifier, self.config['local']['aet'], self.query_model)
                   
            for (status, rsp_identifier) in responses:
                
                if status and status.Status in [0xFF00]:
                    # Status pending
                    pass
                else:
                    # Status Success Warning, Cancel, Failure
                    if self.pbar:
                        self.pbar.update(1)
                    identifier.Status = hex(status.Status)
                    keywords.append('Status')
                    path = os.path.join(self.config['output']['directory'], self.config['output']['database_file'])
                    dataset_to_csv(identifier, path, keywords)

                    

