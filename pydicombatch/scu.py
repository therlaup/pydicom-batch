from pynetdicom import AE
from pynetdicom.sop_class import VerificationSOPClass
from pynetdicom.apps.common import ElementPath
from pydicom.dataset import Dataset
from .common import setup_logging
import os.path
import csv

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
    ModalityWorklistInformationFind,
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind,
    PatientStudyOnlyQueryRetrieveInformationModelFind,
)

def create_dataset(config):
    ds = Dataset()
    try:
        elements = [ElementPath(path) for path in config['request']['elements']]
        for elem in elements:
            ds = elem.update(ds)
    except Exception as exc:
        if logger:
            logger.error(
                'Exception raised trying to parse the supplied keywords'
            )
        raise exc
    return ds


def send_echo(config):
    # Initialise the Application Entity
    ae = AE(ae_title='SAMPLE_AE')
    ae.add_requested_context(VerificationSOPClass)

    # Associate with peer AE
    assoc = ae.associate(config['pacs']['hostname'], 
        config['pacs']['port'],  
        ae_title=config['pacs']['aet'])

    if assoc.is_established:
        # Use the C-ECHO service to send the request
        # returns the response status a pydicom Dataset
        status = assoc.send_c_echo()

        # Check the status of the verification request
        if status:
            # If the verification request succeeded this will be 0x0000
            print('C-ECHO request status: 0x{0:04x}'.format(status.Status))
        else:
            print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()
    else:
        print('Association rejected, aborted or never connected')

def send_find(config):
    APP_LOGGER = setup_logging('findscu')
    # Create query (identifier) dataset
    try:
        # If you're looking at this to see how QR Find works then `identifer`
        # is a pydicom Dataset instance with your query keys, e.g.:
        #     identifier = Dataset()
        #     identifier.QueryRetrieveLevel = 'PATIENT'
        #     identifier.PatientName = ''
        identifier = create_dataset(config)
    except Exception as exc:
        APP_LOGGER.exception(exc)
        raise exc
        sys.exit(1)

    keywords = [ElementPath(path).keyword for path in config['request']['elements']]

    # Create application entity
    # Binding to port 0 lets the OS pick an available port
    ae = AE(ae_title='SAMPLE_AE')

    # Set timeouts
    ae.acse_timeout = 30
    ae.dimse_timeout = 30
    ae.network_timeout = 30

    # Set the Presentation Contexts we are requesting the Find SCP support
    ae.requested_contexts = (
        QueryRetrievePresentationContexts
        + BasicWorklistManagementPresentationContexts
    )

    # Query/Retrieve Information Models
    if config['request']['model'] == 'worklist':
        query_model = ModalityWorklistInformationFind
    elif config['request']['model'] == 'study':
        query_model = StudyRootQueryRetrieveInformationModelFind
    elif config['request']['model'] == 'psonly':
        query_model = PatientStudyOnlyQueryRetrieveInformationModelFind
    else:
        query_model = PatientRootQueryRetrieveInformationModelFind

    
    # Request association with (QR/BWM) Find SCP

    assoc = ae.associate(config['pacs']['hostname'], 
        config['pacs']['port'],  
        ae_title=config['pacs']['aet'],
        max_pdu=16382)

    if assoc.is_established:
        # Send C-FIND request, `responses` is a generator
   
        responses = assoc.send_c_find(identifier, query_model)
        # Used to generate filenames if args.write used
        
        for (status, rsp_identifier) in responses:
            # If `status.Status` is one of the 'Pending' statuses then
            #   `rsp_identifier` is the C-FIND response's Identifier dataset

            if status and status.Status in [0xFF00, 0xFF01]:
                dataset_to_csv(rsp_identifier, config['output']['library_file'], keywords)

        # Release the association
        assoc.release()

def dataset_to_csv(ds, filename, fieldnames):
    write_dict = {}
    for key in fieldnames:
        write_dict[key] = str(ds[key].value)

    if os.path.exists(filename):
        with open(filename, 'a', newline='', ) as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, dialect='excel')
            writer.writerow(write_dict)
    else:
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, dialect='excel')
            writer.writeheader()
            writer.writerow(write_dict)


def add_element_to_list(element_list, key, value):
    if [x if ((x.partition('=')[0] == key) or (x == key)) else None for x in element_list]:
        return [f'{key}={value}' if ((x.partition('=')[0] == key) or (x == key)) else x for x in element_list]
    else:
        element_list.append(f'{key}={value}')
        return element_list

def send_batch_find(config):
    if (os.path.exists(config['request']['elements_batch_file'])):
        with open(config['request']['elements_batch_file'], newline='') as csvfile:
            reader = csv.DictReader(csvfile, dialect='excel')
            for row in reader:
                row_config = config.copy()
                for key in row:
                    row_config['request']['elements'] = add_element_to_list(row_config['request']['elements'], key, row[key])
                
                elements = [ElementPath(path) for path in config['request']['elements']]
                
                send_find(row_config)
    else:
        print('Supplied elements_batch_file does not exist: ', config['request']['elements_batch_file'])