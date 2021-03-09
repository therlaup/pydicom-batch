#!/bin/bash
# A helper script to correctly bind the volumes and ports to the Docker run

function parse_yaml {
   local prefix=$2
   local s='[[:space:]]*' w='[a-zA-Z0-9_]*' fs=$(echo @|tr @ '\034')
   sed -ne "s|^\($s\):|\1|" \
        -e "s|^\($s\)\($w\)$s:$s[\"']\(.*\)[\"']$s\$|\1$fs\2$fs\3|p" \
        -e "s|^\($s\)\($w\)$s:$s\(.*\)$s\$|\1$fs\2$fs\3|p"  $1 |
   awk -F$fs '{
      indent = length($1)/2;
      vname[indent] = $2;
      for (i in vname) {if (i > indent) {delete vname[i]}}
      if (length($3) > 0) {
         vn=""; for (i=0; i<indent; i++) {vn=(vn)(vname[i])("_")}
         printf("%s%s%s=\"%s\"\n", "'$prefix'",vn, $2, $3);
      }
   }'
}


if [ -z "$1" ]; then
    echo "Please provide a config file as argument"
    exit 3
else     
    if [ -f "$1" ]; then
        eval $(parse_yaml $1)
    else 
        echo "$1 does not exist."
        exit 3
    fi
fi

config_file=$(realpath $1)
paths=(
    $config_file
    $output_directory
    $output_anonymization_script
    $output_anonymization_lookup_table
    $output_database_file
    $request_elements_batch_file
    ./data
    ./config
)

volumes=""
for path in "${paths[@]}" ; do
    if [ -f "$path" ] || [ -d "$path" ]; then
        volumes="$volumes -v $(realpath $path):$(realpath $path)"
    else
        volumes="$volumes -v $(dirname $(realpath $path)):$(dirname $(realpath $path))"
    fi
done

echo $volumes

docker run -v $PWD/pydicombatch:/home/pydicom-batch/pydicombatch\
    -p $local_port:$local_port \
    $volumes\
    --rm -it\
    --user $(id -u):$(id -g)\
    pydicom-batch $config_file