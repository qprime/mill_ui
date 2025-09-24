.PHONY: build css watch-css run

build:
	go build ./cmd/server

css:
	npx tailwindcss -c tailwind.config.js -i ./web/static/css/input.css -o ./web/static/css/main.css --minify

watch-css:
	npx tailwindcss -c tailwind.config.js -i ./web/static/css/input.css -o ./web/static/css/main.css --watch

run:
	PORT?=8090
	ACE_BACKEND_URL?=http://127.0.0.1:8080/ace
	PORT=$$PORT ACE_BACKEND_URL=$$ACE_BACKEND_URL go run ./cmd/server
