FROM continuumio/miniconda3

USER root
ENV TERM=vt100
ARG ENV
ENV BUILD_MODE=$ENV

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
	screen \
	dnsutils \
	netcat \
	redis \
	iputils-ping \
    && rm -rf /var/lib/apt/lists/*

RUN conda config --add channels stackless
RUN conda install -y stackless
RUN conda update -y conda
ADD requirements.txt /tmp
RUN pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt
RUN ln -sf /bin/bash /bin/sh

RUN useradd -m -G sudo -d /home/havokmud -s /bin/bash -c "HavokMud Account" havokmud
WORKDIR /home/havokmud
RUN chmod 700 /home/havokmud
RUN mkdir -p /etc/sudoers.d
RUN echo "havokmud ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/havokmud
ADD src /home/havokmud/src/havokmud
ADD docker/aws-$ENV /home/havokmud/.aws
ADD docker/config-$ENV /home/havokmud/.havokmud
RUN chown -R havokmud /home/havokmud
USER havokmud
EXPOSE 3000

WORKDIR /home/havokmud/src/havokmud
