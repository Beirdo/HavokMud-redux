FROM continuumio/miniconda3

USER root
ENV TERM=vt100

RUN apt-get update \
    && apt-get install -y \
	net-tools \
	python3 \
	apt-transport-https \
	ca-certificates \
	curl \
	gnupg-agent \
	software-properties-common \
	less \
	sudo \
	apt-utils \
	vim-tiny \
    && rm -rf /var/lib/apt/lists/*

RUN conda config --add channels stackless
RUN conda install -y stackless
RUN conda update -y conda
RUN conda install -y boto3 jinja2
RUN pip install ansicolors

RUN useradd -m -G sudo -d /home/havokmud -s /bin/bash -c "HavokMud Account" havokmud
WORKDIR /home/havokmud
RUN chmod 700 /home/havokmud
RUN mkdir -p /etc/sudoers.d
RUN echo "havokmud ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/havokmud
ADD src /home/havokmud/src/havokmud
RUN chown -R havokmud /home/havokmud
USER havokmud
EXPOSE 3000

WORKDIR /home/havokmud/src/havokmud
