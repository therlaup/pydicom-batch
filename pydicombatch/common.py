import yaml
from .scu import process_request_batch
from .scp import SCP
import os

def pydicombatch(config_file):
    with open(config_file) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

        print('Running extraction defined in: ', config_file)

        if config['request']['type'].lower() == 'c-move':
            scp = SCP(config)
            scp.start_server()
        process_request_batch(config)

        if config['request']['type'].lower() == 'c-move':
            scp.stop_server()

        filepath_requests_failed = os.path.join(config['output']['directory'], 'requests.failed')
        if os.path.exists(filepath_requests_failed):
            print('Failed requests detected. To re-try failed request, re-run batch request.')