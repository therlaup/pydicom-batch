
import sys
from .common import pydicombatch

print("\n█▀█ █▄█ █▀▄ █ █▀▀ █▀█ █▀▄▀█   █▄▄ ▄▀█ ▀█▀ █▀▀ █░█\n█▀▀ ░█░ █▄▀ █ █▄▄ █▄█ █░▀░█   █▄█ █▀█ ░█░ █▄▄ █▀█\n")

if len(sys.argv) != 2:
    help_string = 'Usage: pydicombatch.py <config file>'
    print(help_string)
else:
    config_file = sys.argv[1]
    pydicombatch(config_file)
