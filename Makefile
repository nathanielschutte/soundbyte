
LOG_DIR=/var/log/soundbyte
PROJECT_NAME=soundbyte

.PHONY: all build run

build: .env
	docker build -t $(PROJECT_NAME):latest --target soundbyte --file docker/Dockerfile .

run: build
	docker run -d --rm \
		-v $(LOG_DIR):/var/log/soundbyte \
		-v $(PWD)/soundbits:/app/soundbits \
		-v $(PWD)/storage:/app/storage \
		--name "$(PROJECT_NAME)" \
		$(PROJECT_NAME):latest

deploy:
	bash deploy.sh
