docker-image:
	docker image build -t havokmud:latest . -f docker/Dockerfile

docker-test-image:
	docker image build -t havokmud:latest . -f docker/Dockerfile --build-arg ENV=testing
