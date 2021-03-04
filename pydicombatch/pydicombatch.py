
import sys
import getopt
import os
sys.path.append(os.getcwd()) 

import numpy as np
import yaml
import pydicombatch as pb
from pynetdicom import AE

config = ''

try:
    opts, args = getopt.getopt(argv,"hi:o:",["config=","ofile="])
except getopt.GetoptError:
    print 'main.py -i <inputfile> -o <outputfile>'
    sys.exit(2)
for opt, arg in opts:
    if opt == '-h':
        print 'test.py -i <inputfile> -o <outputfile>'
        sys.exit()
    elif opt in ("-i", "--ifile"):
        inputfile = arg
    elif opt in ("-o", "--ofile"):
        outputfile = arg


with open('./config/export-config.yml') as file:
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