import os
import sys
from .common import setup_logging


from pydicom.dataset import Dataset

from pynetdicom import (
    AE, evt, QueryRetrievePresentationContexts, AllStoragePresentationContexts
)
from pynetdicom.apps.common import create_dataset, setup_logging
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

__version__ = '0.0.1'


def handle_store(event, config, app_logger):
    """Handle a C-STORE request.
    Parameters
    ----------
    event : pynetdicom.event.event
        The event corresponding to a C-STORE request.
    config : 
        config data
    app_logger : logging.Logger
        The application's logger.
    Returns
    -------
    status : pynetdicom.sop_class.Status or int
        A valid return status code, see PS3.4 Annex B.2.3 or the
        ``StorageServiceClass`` implementation for the available statuses
    """

    try:
        ds = event.dataset
        # Remove any Group 0x0002 elements that may have been included
        ds = ds[0x00030000:]
    except Exception as exc:
        app_logger.error("Unable to decode the dataset")
        app_logger.exception(exc)
        # Unable to decode dataset
        return 0x210

    # Add the file meta information elements
    ds.file_meta = event.file_meta

    # Because pydicom uses deferred reads for its decoding, decoding errors
    #   are hidden until encountered by accessing a faulty element
    try:
        sop_class = ds.SOPClassUID
        sop_instance = ds.SOPInstanceUID
    except Exception as exc:
        app_logger.error(
            "Unable to decode the received dataset or missing 'SOP Class "
            "UID' and/or 'SOP Instance UID' elements"
        )
        app_logger.exception(exc)
        # Unable to decode dataset
        return 0xC210

    try:
        # Get the elements we need
        mode_prefix = SOP_CLASS_PREFIXES[sop_class][0]
    except KeyError:
        mode_prefix = 'UN'

    filename = f'{mode_prefix}.{sop_instance}'
    app_logger.info(f'Storing DICOM file: {filename}')    

    status_ds = Dataset()
    status_ds.Status = 0x0000

    # Try to save to output-directory
    if config['output']['directory'] is not None:
        filename = os.path.join(config['output']['directory'], filename)
        try:
            os.makedirs(config['output']['directory'], exist_ok=True)
        except Exception as exc:
            app_logger.error('Unable to create the output directory:')
            app_logger.error(f"    {config['output']['directory']}")
            app_logger.exception(exc)
            # Failed - Out of Resources - IOError
            status_ds.Status = 0xA700
            return status_ds

    if os.path.exists(filename):
        app_logger.warning('DICOM file already exists, overwriting')        
        
    try:
        if event.context.transfer_syntax == DeflatedExplicitVRLittleEndian:
            # Workaround for pydicom issue #1086
            with open(filename, 'wb') as f:
                f.write(b'\x00' * 128)
                f.write(b'DICM')
                f.write(write_file_meta_info(f, event.file_meta))
                f.write(encode(ds, False, True, True))
        else:
            # We use `write_like_original=False` to ensure that a compliant
            #   File Meta Information Header is written
            ds.save_as(filename, write_like_original=False)

        status_ds.Status = 0x0000  # Success
    except IOError as exc:
        app_logger.error('Could not write file to specified directory:')
        app_logger.error(f"    {os.path.dirname(filename)}")
        app_logger.exception(exc)
        # Failed - Out of Resources - IOError
        status_ds.Status = 0xA700
    except Exception as exc:
        app_logger.error('Could not write file to specified directory:')
        app_logger.error(f"    {os.path.dirname(filename)}")
        app_logger.exception(exc)
        # Failed - Out of Resources - Miscellaneous error
        status_ds.Status = 0xA701

    return status_ds


def start_server(ae, config):
    APP_LOGGER = setup_logging('scp')
    APP_LOGGER.debug(f'pydicombatch c-store server v{__version__}')
    
    transfer_syntax = ALL_TRANSFER_SYNTAXES[:]
    store_handlers = [(evt.EVT_C_STORE, handle_store, [config, APP_LOGGER])]
    ae.ae_title = config['local']['aet']
    for cx in AllStoragePresentationContexts:
        ae.add_supported_context(cx.abstract_syntax, transfer_syntax)

    scp = ae.start_server(
        ('', config['local']['port']), block=False, evt_handlers=store_handlers
        )
    return scp
