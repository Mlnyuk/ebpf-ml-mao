PYTHON ?= python3
IMAGE ?= ghcr.io/mlnyuk/ebpf-ml-mao:step14

.PHONY: test render-step14 dry-run-step14 build-image deploy-step14

test:
	$(PYTHON) -m unittest discover -s tests -v

render-step14:
	kubectl kustomize deploy/yaml/step14

dry-run-step14:
	kubectl apply --dry-run=client -k deploy/yaml/step14

build-image:
	docker build -t $(IMAGE) .

deploy-step14:
	kubectl apply -k deploy/yaml/step14
