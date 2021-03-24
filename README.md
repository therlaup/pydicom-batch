# PYDICOM batch export
This project provides python-based batch image export scripts from a PACS server compliant with the DICOM procotol. Data extractions can be used to create a local database of available DICOM instances on the PACS and can also be used to transfer images to a local hard drive. These scripts were created as part of data science projects involving artificial intelligence methods, which require the creation of large-scale datasets of medical images.

The scripts are based on the Pydicom (https://github.com/pydicom/pydicom) and Pynetdicom (https://github.com/pydicom/pynetdicom).

Extractions are defined in YAML configuration files and batches of requests are stored in CSV files. Examples are provided in the [configuration directory](config). We provide some explanation [below](#config).

There are two options available to run PYDICOM batch: (1) Docker container or (2) bare metal Anaconda. Both are supported but the docker-based approach may be simpler to use without affecting your base system. 

## Quick start

You will need to have a system with git installed. We have tested the scrips using Ubuntu and the Windows Subsystem for Linux 2 (https://docs.microsoft.com/en-us/windows/wsl/install-win10). You will first need to clone the repository using:

```bash
git clone https://github.com/therlaup/pydicom-batch.git
```

### Option 1: Docker container based installation

#### Install Docker

For installation instruction for Docker depending on your system see https://docs.docker.com/get-docker/. 

#### Building docker container

We have included a build script for the Docker container at ``bin/build-docker-container.sh``.

```bash
cd pydicom-batch
./bin/build-docker-container.sh
```

After the build is complete, you will have an image called ``pydicom-batch`` available.

If you are using a linux workstation, you are essentially done at this time and can skip to the usage section.

If you are using Windows with WSL 2, you will need to set up portforwarding. Within the WSL 2 terminal, use ifconfig to obtain the IP address of the virtual machine. In a powershell terminal with administrator rights, then execute:

```powershell
PS> netsh interface portproxy add v4tov4 listenport=<local port> listenaddress=0.0.0.0 connectport=<local port> connectaddress=<WSL IP address>
```

#### Run extraction

We provide bash scripts that are useful to correctly bind the ports and volumes defined in your configuration files.

```bash
./bin/run-docker-extraction.sh <extraction configuration file>
```


### Option 2: Anaconda installation

Alternatively to the Docker installation, you can install a local version of Anaconda. You will first need to install Miniconda using the instructions at https://docs.conda.io/en/latest/miniconda.html 

Once you have your local installation, use the following commands to install dependencies in the Anaconda prompt:

```bash
cd pydicom-batch
conda update --name base conda
conda env create --file config/environment.yaml
conda clean -afy 
```

You will then have a conda environement called ``pydicom-batch`` ready to use. It can be activated using:

```bash
conda activate pydicom-batch
```

Finally, to execute the script, you may use:
```bash
conda run --no-capture-output --name pydicom-batch python -u -m pydicombatch <extraction configuration file>
```

The format of the configuration file is described [below](#config)

## Important DICOM concepts

As you will notice, the DICOM standard involves a large number of acronyms, which may be confusing to the first time user. We provide here a brief primer. 

The [DICOM protocol](https://www.dicomstandard.org/) defines several abstractions to standardize communication of medical images between devices. For example, a device can be viewing workstation, an archiving server, an imaging modality, etc. For our purpose, we need to understand some basic concepts relating to the DICOM standard.

### DICOM dataset format

The DICOM format stores information into datasets. A given dataset includes several elements, each of which contains a piece of information. For example, a chest radiograph would be stored as a dataset with the study date, the patient name, and the pixel data, each stored as a separate element. Elements are defined in the DICOM standard using tags with the format (XXXX,XXXX), where each XXXX is an hexadecimal number. Elements also have standard names defined in a [data dictionary](http://dicom.nema.org/medical/dicom/current/output/html/part06.html). Each element can only store information in a specific format, which is defined base on it [Value Representation (VR)](http://dicom.nema.org/dicom/2013/output/chtml/part05/sect_6.2.html).

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

## <a name="config"></a> Extraction configuration files

Extractions are defined in YAML files. We provide example files in the config directory. Note that path defined in configuration files should be absolute.

### Sample C-FIND request

The purpose of a C-FIND extraction is to generate a list of DICOM instances available on the PACS server based on defined criteria:

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

### Sample C-MOVE request

The purpose of a C-MOVE extraction is to transfer DICOM instance to our local workstation.

We provide the following additional features:
* Anonymization: If you would like the files to be automatically anonymized after transfer, you need to define an anonymization script. We use the [RSNA DICOM Anonymizer](https://mircwiki.rsna.org/index.php?title=The_CTP_DICOM_Anonymizer) for this purpose. This software allows you to also define a 'lookup table', which will map the value of a particular DICOM field to a correponding value after anonymization ([See the example](https://mircwiki.rsna.org/index.php?title=The_CTP_DICOM_Anonymizer#.40lookup.28ElementName.2CKeyType.29)).
* Scheduling: If you want your extraction to run at a specific time of the day, so as not to interfere with the PACS server, you can set the `start_time` and `end_time` in 24 hour format HH:mm. The extraction will only proceed if the current time is between `start_time` and `end_time`. If executed outside of these hours, the script will wait until `start_time` to perform the extraction. The example configuration below would result in requests being sent between 5:13pm and 5:15pm.
* Output directory structure: You may define the directory where DICOM files should be saved and you can define the structure of the subdirectories to be created based on DICOM keywords. For example, if we use the configuration file shown below, a DICOM file with PatientID = 0123, StudyInstanceUID = 1.25542.324524, and InstanceNumber = 1 would be stored at `/home/therlaup/DICOM-batch-export/data/0123/1.25542.324524/1.dcm`.
* Resuming: You can stop the extraction by pressing CRTL+C at any point. The extraction can be resumed later by re-executing the script.

This is an example C-MOVE configuration file:
```yaml
pacs:
  hostname: 172.29.144.1
  port: 4242
  aet: ORTHANC
local:
  port: 4000
  aet: SAMPLE_AE
request:
  type: c-move
  model: patient
  threads: 1
  throttle_time: 0.0
  elements_batch_file: /home/therlaup/DICOM-batch-export/config/sample-c-move-batch.csv
  elements:
    - StudyInstanceUID
    - SeriesInstanceUID
    - QueryRetrieveLevel=SERIES 
schedule:
  enabled: true
  start_time: '17:13'
  end_time: '17:15'
  timezone: America/New_York
anonymization:
  enabled: true
  script: /home/therlaup/DICOM-batch-export/config/sample-dicom-anonymizer.script
  lookup_table: /home/therlaup/DICOM-batch-export/config/sample-lookup-table.properties
output:
  directory: /home/therlaup/DICOM-batch-export/data
  database_file: /home/therlaup/DICOM-batch-export/data/database-c-move.csv
  directory_structure: PatientID/StudyInstanceUID
  filename: InstanceNumber
  decompress: True
```
