.PHONY: build css watch-css run

# Defaults (can be overridden on the CLI)
PORT ?= 8090
ACE_BACKEND_URL ?= https://127.0.0.1:8080/ace
# For local self-signed Flask certs, allow insecure backend TLS (client-side).
ACE_TLS_INSECURE ?= 1

build:
	go build ./cmd/server

css:
	npx tailwindcss -c tailwind.config.js -i ./web/static/css/input.css -o ./web/static/css/main.css --minify

watch-css:
	npx tailwindcss -c tailwind.config.js -i ./web/static/css/input.css -o ./web/static/css/main.css --watch

run:
	PORT=$$PORT ACE_BACKEND_URL=$$ACE_BACKEND_URL ACE_TLS_INSECURE=$$ACE_TLS_INSECURE \
		go run ./cmd/server
