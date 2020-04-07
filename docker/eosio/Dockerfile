FROM ubuntu:18.04

USER root
ENV TERM=vt100
ARG ENV
ENV BUILD_MODE=$ENV

ADD docker/eosio/debs /tmp
RUN apt-get update \
    && apt-get install -y \
	net-tools \
	python3 \
	apt-transport-https \
	ca-certificates \
	curl \
	wget \
	less \
	sudo \
	apt-utils \
	vim-tiny \
	screen \
	dnsutils \
	netcat \
	iputils-ping \
	cmake \
	git-core \
	build-essential \
	g++ \
	python3-pip \
	libssl1.0-dev \
	jq \
	psmisc \
    /tmp/eosio_2.0.4-1-ubuntu-18.04_amd64.deb \
    /tmp/eosio.cdt_1.6.3-1-ubuntu-18.04_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -G sudo -d /home/eosio -s /bin/bash -c "EOSIO Account" eosio
WORKDIR /home/eosio
RUN chmod 700 /home/eosio
RUN mkdir -p /etc/sudoers.d
RUN echo "eosio ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/eosio
RUN mkdir /home/eosio/src
RUN chown -R eosio /home/eosio

USER eosio

WORKDIR /home/eosio/src
RUN git clone https://github.com/EOSIO/eosio.contracts.git eosio.contracts-1.8.x
WORKDIR /home/eosio/src/eosio.contracts-1.8.x
RUN git checkout release/1.8.x
RUN echo y | ./build.sh
ENV EOSIO_OLD_CONTRACTS_DIRECTORY /home/eosio/src/eosio.contracts-1.8.x/build/contracts

USER root

RUN apt-get remove -y eosio.cdt && apt-get update && apt-get install -y \
    /tmp/eosio.cdt_1.7.0-1-ubuntu-18.04_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

USER eosio

WORKDIR /home/eosio/src
RUN git clone https://github.com/EOSIO/eosio.contracts.git eosio.contracts-1.9.x
WORKDIR /home/eosio/src/eosio.contracts-1.9.x
RUN git checkout release/1.9.x
RUN echo y | ./build.sh
ENV EOSIO_CONTRACTS_DIRECTORY /home/eosio/src/eosio.contracts-1.9.x/build/contracts

RUN pip3 install numpy
ADD docker/eosio/eosio /home/eosio/eosio
WORKDIR /home/eosio/eosio
RUN ln -sf /home/eosio/nodes nodes

# keosd
EXPOSE 6666

# nodeos
EXPOSE 8000
