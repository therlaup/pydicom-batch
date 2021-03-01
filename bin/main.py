
import sys
import os
sys.path.append(os.getcwd()) 

import numpy as np
import yaml
import pydicombatch as pb
from pynetdicom import AE


with open('./config/sample-export-config.yml') as file:
    config = yaml.load(file, Loader=yaml.FullLoader)

    print(config)
    print(config['pacs']['aet'])
    ae = AE()
    # scp = pb.start_server(ae, config)

        # if scp:
    #     scp.shutdown()
    # pb.send_echo(config)
    # print(pb.create_dataset(config))

    if (config['request']['type'].lower() == 'c-find'):
        if ('elements_batch_file' in config['request']):
            pb.send_batch_find(config)
        else:
            pb.send_find(config)