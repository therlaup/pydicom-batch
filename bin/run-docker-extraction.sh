#!/bin/bash
# A helper script to correctly bind the 

# A POSIX variable
set -o errexit -o pipefail -o noclobber -o nounset
! getopt --test > /dev/null 
if [[ ${PIPESTATUS[0]} -ne 4 ]]; then
    echo 'I’m sorry, `getopt --test` failed in this environment.'
    exit 1
fi

OPTIONS=hc:b:o:
LONGOPTS=help,config-file:,batch-file:,output_directory:

! PARSED=$(getopt --options=$OPTIONS --longoptions=$LONGOPTS --name "$0" -- "$@")
if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
    # e.g. return value is 1
    #  then getopt has complained about wrong arguments to stdout
    exit 2
fi
# read getopt’s output this way to handle the quoting right:
eval set -- "$PARSED"


config_file=""
batch_file=""
output_directory=""
help=""
b=""
c=""
o=""
# now enjoy the options in order and nicely split until we see --
while true; do
    case "$1" in
        -b|--batch-file)
            batch_file=$(realpath $2)
            b="-b"
            shift 2
            ;;
        -c|--config-file)
            config_file=$(realpath $2)
            c="-c"
            shift 2
            ;;
        -o|--output_directory)
            output_directory=$(realpath $2)
            o="-o"
            shift 2
            ;;
        -h|--help)
            help="--help"
            shift 1
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "Programming error"
            exit 3
            ;;
    esac
done


docker run \
    -v $config_file:$config_file\
    -v $batch_file:$batch_file\
    -v $output_directory:$output_directory\
    --rm -ti\
    --user $(id -u):$(id -g)\
    dicom-batch-query $help $c $config_file $b $batch_file $o $output_directory