docker-image:
	docker image build -t havokmud:0.0 . -f docker/Dockerfile

docker-test-image:
	docker image build -t havokmud:0.0 . -f docker/Dockerfile --build-arg ENV=testing
