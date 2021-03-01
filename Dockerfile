FROM continuumio/miniconda3:latest

ENV PYTHONDONTWRITEBYTECODE=true
ENV APP_HOME /app

WORKDIR $APP_HOME
COPY ./config $APP_HOME/config

RUN conda update --name base conda &&\
    conda env create --file environment.yml \
    && conda clean -afy 
RUN find /opt/conda/ -follow -type f -name '*.a' -delete \
    && find /opt/conda/ -follow -type f -name '*.pyc' -delete \
    && find /opt/conda/ -follow -type f -name '*.js.map' -delete 

SHELL ["conda", "run", "--name", "dicom-batch-export", "/bin/bash", "-c"]

ENTRYPOINT ["conda", "run", "--name", "dicom-batch-export", "python", "bin/main.py"]

