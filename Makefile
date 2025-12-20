.PHONY: build generate clean

IMAGE_NAME = garmin-summary

build:
	docker build -t $(IMAGE_NAME) .

generate: build
	docker run --rm -v $(PWD)/data:/app/data $(if $(YEAR),-e YEAR=$(YEAR)) $(IMAGE_NAME)

clean:
	rm -f data/garmin-*.png