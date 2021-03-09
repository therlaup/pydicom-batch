
import sys
import getopt
import os
sys.path.append(os.getcwd()) 

import numpy as np
import yaml
from .scu import process_request_batch
from .scp import SCP
from pynetdicom import AE

help_string = 'Usage: pydicombatch.py <config file>'

# os.system('java -jar DicomAnonymizerTool/DAT.jar')

config_file = sys.argv[1]


with open(config_file) as file:
    config = yaml.load(file, Loader=yaml.FullLoader)

    print('Running extraction defined in: ', config_file)
    
    scp = SCP(config)
    scp.start_server()
    process_request_batch(config)
    # scp.stop_server()

        # if scp:
    #     scp.shutdown()
    # pb.send_echo(config)
    # print(pb.create_dataset(config))
    


    # if (config['request']['type'].lower() == 'c-find'):
    #     if ('elements_batch_file' in config['request']):
    #         send_batch_find(config)
    #     else:
    #         send_find(config)