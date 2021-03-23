import yaml
from .scu import process_request_batch
from .scp import SCP
import os
import sys

def pydicombatch(config_file):
    with open(config_file) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

        print('Running extraction defined in: ', config_file)

        if config['request']['type'].lower() == 'c-move':
            scp = SCP(config)
            scp.start_server()
        try:
            process_request_batch(config)
        except KeyboardInterrupt:
            print('\b\b\r')
            print('\nExtraction stopped. To resume extraction, please re-execute the script.')
            if config['request']['type'].lower() == 'c-move':
                scp.stop_server()

            filepath_requests_failed = os.path.join(config['output']['directory'], 'requests.failed')
            if os.path.exists(filepath_requests_failed):
                print('Failed requests detected. To re-try failed request, re-run batch request.')
            sys.exit(0)