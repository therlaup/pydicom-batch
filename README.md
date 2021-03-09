# DICOM batch export
This project provides python-based batch image export scripts from a PACS server compliant with the DICOM procotol. Data extractions can be used to create a local database of available DICOM instances on the PACS and can also be used to transfer images to a local hard drive. These scripts were created as part of data science projects involving artificial intelligence methods for the creation of large-scale datasets of medical images.

The scripts are based on the Pydicom (https://github.com/pydicom/pydicom) and Pynetdicom (https://github.com/pydicom/pynetdicom).

## Installation

You will need to have a system with git installed. We have tested the scrips using Ubuntu and the Windows Subsystem for Linux 2 (https://docs.microsoft.com/en-us/windows/wsl/install-win10). You will first need to clone the repository using:

```bash
git clone https://github.com/therlaup/DICOM-batch-export.git
```

There are two options available to run the DICOM extractor: (1) Docker container or (2) bare metal Anaconda. Both are supported but the docker-based approach may be simpler to use without affecting your base system. 

### Option 1: Docker container based installation

#### Install Docker

For installation instruction for Docker depending on your system see https://docs.docker.com/get-docker/. 

#### Building docker container

We have included a build script for the Docker container at ``bin/build-docker-container.sh``.

```bash
cd DICOM-batch-export
./bin/build-docker-container.sh
```

After the build is complete, you will have an image called ``dicom-batch-query`` available.

### Option 2: Anaconda installation

Alternatively to the Docker installation, you can install a local version of Anaconda. You will first need to install Miniconda usign the instructions at https://docs.conda.io/en/latest/miniconda.html 

Once you have your local installation, use the following commands to install dependencies:

```bash
cd DICOM-batch-export
conda update --name base conda
conda env create --file config/environment.yaml
conda clean -afy 
```

You will then have a conda environement called ``dicom-batch-export`` ready to use.

## Important concepts

As you will notice, the DICOM standard involved a large number of acronyms, which may be confusing to the first time user. We provide here a brief primer. 

The [DICOM protocol](https://www.dicomstandard.org/) defines several abstractions to standardize communication of medical images between devices. For example, a device can be viewing workstation, an archiving server, an imaging modality, etc. For our purpose, we need to understand some basic concepts relating to the DICOM standard.

### DICOM format

The DICOM format stores information into datasets. A given dataset includes several elements, each of which contains a piece of information. For example, a chest radiograph would be stored as a dataset with the study date, the patient name, and the pixel data, each stored as a separate element. Elements are defined in the DICOM standard using tags of the format (XXXX,XXXX), where each XXXX is an hexadecimal number. Elements also have standard names defined in a [data dictionary](http://dicom.nema.org/medical/dicom/current/output/html/part06.html). Each element can only store information in a specific format, which is defined base on it [Value Representation (VR)](http://dicom.nema.org/dicom/2013/output/chtml/part05/sect_6.2.html).

DICOM datasets are general and can be used to store images and their metadata but also can be used to define requests sent to a PACS server.

### DICOM communication

DICOM is based on two-way communication between a device that sends information and one that receives information. These roles are called Service Class User (SCU) for the device that generate requests and Service Class Provider (SCP) for a device that responds to requests. A given device may have both roles if it generates and responds to requests. 

SCU and SCP are types of Applications Entities (AE). Usually, PACS servers will keep a list of AE with which it is authorized to communicate. The AE is defined with its IP address, the TCP/IP port which is used for communication, as well as an application entity title, which is a string of a maximum of 30 characters that is locally unique.

DICOM communitation involves two steps: (1) an association negociation and (2) an operation.

During the association negociation, the SCU requests an accociation with the SCP based on the type of operation it wants to conduct. DICOM defines these operations as a Service-Object Pair (SOP)

The types of operations that are allowed are called DICOM Message Service Element (DIMSE). In our case, we are interested in composite operations:
* C-STORE: a push command where the SCU has an object to be transfered to the SCP. For example, a CT scanner acting as SCU has to push images it generated to the PACS server acting as SCP.
* C-FIND: a query command to match a series of attributes and reponds with matching data. This can be used to search a PACS server for images matching certain criteria. The server responds only with the DICOM attributes requested, not the entire DICOM instance. For example, a workstation (SCU) could send a C-FIND command to search for studies with a certain PatientID and request a list of attributes such as the Study Date, Study description, etc; the server would answer with the list of studies 
* C-GET: a fetch command that will return the full dataset of the matching instances. This would be a useful command for our purpose. Unfortunately, very few PACS servers support this command. A C-MOVE is used instead.
* C-MOVE: a move request involves three entites. A first entity instructs a second entity to transfer stored instances to a third entity using a C-STORE operation. In our case, the first and third entities are the same device — i.e., our local machine — and the second entity is the PACS server. 

## Usage

Batch operations are defined in YAML files. The files must include 4 sections:

```yaml
pacs:
  hostname: 172.20.112.1            # Hostname of the PACS server
  port: 4242                        # Post of the PACS server
  aet: ORTHANC                      # Application entity title of the PACS server
local:
  port: 4000                        # Post of the local storage SCP
  aet: SAMPLE_AE                    # Application entity title of the local storage SCP
request:
  type: c-find                      # The type of operation to process: c-find or c-move
  model: patient                    # The query/retrieve information model: patient or study
  elements_batch_file: ./config/sample_batch.csv # File path of the batch of elements ot process. If omitted, a single c-find is processed.
  elements:                         # Elements common to the entire batch in format 'keyword=value', 
                                    # these elements will be included in the output data of a c-find
    - PatientID=02004950
    - PatientName
    - Date
    - StudyTime
    - StudyDate
    - AccessionNumber
    - StudyInstanceUID
    - QueryRetrieveLevel=SERIES
    - ModalitiesInStudy
    - (0020,1208)
    - (0020,1206)
    - (0008,1030)
    - (0008,103E)
output:
  library_file: library.csv         # File path to the CSV file storing the results of c-find requests
  directory: ./data/dicom           # Directoty in which to store DICOM files transfered using c-move 
  directory_structure: PatientID/StudyInstanceUID/  # Directory structure generated in the output directory
```

The 

## Under development
We will soon be adding the abtch C-MOVE functionality.
