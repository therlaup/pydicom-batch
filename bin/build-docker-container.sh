#!/bin/bash

docker build\
    --build-arg UID=$(id -u)\
    --build-arg GID=$(id -g)\
    --tag pydicom-batch:latest\
    --file Dockerfile .