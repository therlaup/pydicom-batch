FROM continuumio/miniconda3:latest

ARG UID=1000
ARG GID=1000

ENV PYTHONDONTWRITEBYTECODE=true
ENV APP_HOME /home/pydicom-batch

RUN groupadd --gid $GID -o pydicom-batch
RUN adduser --uid $UID --gid $GID --disabled-password --gecos '' pydicom-batch

RUN chown pydicom-batch -R /opt/conda

ENV LANG='en_US.UTF-8' LANGUAGE='en_US:en' LC_ALL='en_US.UTF-8'

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata curl ca-certificates fontconfig locales \
    && echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen \
    && locale-gen en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_VERSION jdk-11.0.10+9

RUN set -eux; \
    ARCH="$(dpkg --print-architecture)"; \
    case "${ARCH}" in \
       aarch64|arm64) \
         ESUM='420c5d1e5dc66b2ed7dedd30a7bdf94bfaed10d5e1b07dc579722bf60a8114a9'; \
         BINARY_URL='https://github.com/AdoptOpenJDK/openjdk11-binaries/releases/download/jdk-11.0.10%2B9/OpenJDK11U-jdk_aarch64_linux_hotspot_11.0.10_9.tar.gz'; \
         ;; \
       armhf|armv7l) \
         ESUM='34908da9c200f5ef71b8766398b79fd166f8be44d87f97510667698b456c8d44'; \
         BINARY_URL='https://github.com/AdoptOpenJDK/openjdk11-binaries/releases/download/jdk-11.0.10%2B9/OpenJDK11U-jdk_arm_linux_hotspot_11.0.10_9.tar.gz'; \
         ;; \
       ppc64el|ppc64le) \
         ESUM='e1d130a284f0881893711f17df83198d320c16f807de823c788407af019b356b'; \
         BINARY_URL='https://github.com/AdoptOpenJDK/openjdk11-binaries/releases/download/jdk-11.0.10%2B9/OpenJDK11U-jdk_ppc64le_linux_hotspot_11.0.10_9.tar.gz'; \
         ;; \
       s390x) \
         ESUM='b55e5d774bcec96b7e6ffc8178a17914ab151414f7048abab3afe3c2febb9a20'; \
         BINARY_URL='https://github.com/AdoptOpenJDK/openjdk11-binaries/releases/download/jdk-11.0.10%2B9/OpenJDK11U-jdk_s390x_linux_hotspot_11.0.10_9.tar.gz'; \
         ;; \
       amd64|x86_64) \
         ESUM='ae78aa45f84642545c01e8ef786dfd700d2226f8b12881c844d6a1f71789cb99'; \
         BINARY_URL='https://github.com/AdoptOpenJDK/openjdk11-binaries/releases/download/jdk-11.0.10%2B9/OpenJDK11U-jdk_x64_linux_hotspot_11.0.10_9.tar.gz'; \
         ;; \
       *) \
         echo "Unsupported arch: ${ARCH}"; \
         exit 1; \
         ;; \
    esac; \
    curl -LfsSo /tmp/openjdk.tar.gz ${BINARY_URL}; \
    echo "${ESUM} */tmp/openjdk.tar.gz" | sha256sum -c -; \
    mkdir -p /opt/java/openjdk; \
    cd /opt/java/openjdk; \
    tar -xf /tmp/openjdk.tar.gz --strip-components=1; \
    rm -rf /tmp/openjdk.tar.gz;

ENV JAVA_HOME=/opt/java/openjdk \
    PATH="/opt/java/openjdk/bin:$PATH"

WORKDIR $APP_HOME
USER pydicom-batch

COPY --chown=pydicom-batch:pydicom-batch environment.yml $APP_HOME
COPY --chown=pydicom-batch:pydicom-batch ./pydicombatch $APP_HOME/pydicombatch

RUN conda update --name base conda &&\
    conda env create --file $APP_HOME/environment.yml \
    && conda clean -afy\
    && find /opt/conda/ -follow -type f -name '*.a' -delete \
    && find /opt/conda/ -follow -type f -name '*.pyc' -delete \
    && find /opt/conda/ -follow -type f -name '*.js.map' -delete 

ADD --chown=pydicom-batch:pydicom-batch https://dl.dropboxusercontent.com/s/fhhhdkfe730gwp3/DAT.tar.gz $APP_HOME
RUN tar -zxvf DAT.tar.gz

SHELL ["conda", "run", "--name", "pydicom-batch", "/bin/bash", "-c"]

ENTRYPOINT ["conda", "run", "--no-capture-output", "--name", "pydicom-batch", "python", "-u", "-m", "pydicombatch"]

