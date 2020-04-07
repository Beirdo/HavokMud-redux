docker-image:
	docker image build -t havokmud:latest . -f docker/Dockerfile

docker-test-image:
	docker image build -t havokmud:latest . -f docker/Dockerfile --build-arg ENV=testing

docker-test-eosio-image:	eosio-debs
	docker image build -t eosio:latest . -f docker/eosio/Dockerfile --build-arg ENV=testing

EOSIO_DEBS  = docker/eosio/debs/eosio_2.0.4-1-ubuntu-18.04_amd64.deb
EOSIO_DEBS += docker/eosio/debs/eosio.cdt_1.6.3-1-ubuntu-18.04_amd64.deb
EOSIO_DEBS += docker/eosio/debs/eosio.cdt_1.7.0-1-ubuntu-18.04_amd64.deb

eosio-debs:	${EOSIO_DEBS}

docker/eosio/debs/eosio_2.0.4-1-ubuntu-18.04_amd64.deb:
	wget https://github.com/eosio/eos/releases/download/v2.0.4/eosio_2.0.4-1-ubuntu-18.04_amd64.deb -O docker/eosio/debs/eosio_2.0.4-1-ubuntu-18.04_amd64.deb

docker/eosio/debs/eosio.cdt_1.6.3-1-ubuntu-18.04_amd64.deb:
	wget https://github.com/eosio/eosio.cdt/releases/download/v1.6.3/eosio.cdt_1.6.3-1-ubuntu-18.04_amd64.deb -O docker/eosio/debs/eosio.cdt_1.6.3-1-ubuntu-18.04_amd64.deb

docker/eosio/debs/eosio.cdt_1.7.0-1-ubuntu-18.04_amd64.deb:
	wget https://github.com/eosio/eosio.cdt/releases/download/v1.7.0/eosio.cdt_1.7.0-1-ubuntu-18.04_amd64.deb -O docker/eosio/debs/eosio.cdt_1.7.0-1-ubuntu-18.04_amd64.deb

