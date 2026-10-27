# Convenience targets. Everything here works from a fresh clone (after `git lfs pull`).
COMPOSE ?= docker compose
PLATFORMS ?= linux/amd64,linux/arm64
GPU_FILES = -f docker-compose.yml -f docker-compose.gpu.yml

.PHONY: help check lfs build up up-gpu down health render ui-check scale buildx-multiarch models tts clean-volumes

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

check:           ## FAIL on symlinks, host paths or LFS pointers (also runs inside every image build)
	./scripts/check-paths.sh . --lfs

lfs:             ## fetch the LFS art (needed before build)
	git lfs install --local && git lfs pull

build: check     ## build the runtime + renderer images for this machine
	$(COMPOSE) build

up: check        ## start the renderer UI + render worker(s), CPU
	$(COMPOSE) up -d --wait

up-gpu: check    ## same, with the NVIDIA GPU overlay
	$(COMPOSE) $(GPU_FILES) up -d --wait

scale:           ## e.g. make scale N=4
	$(COMPOSE) up -d --wait --scale worker=$(or $(N),2)

down:            ## stop and remove containers (volumes are kept)
	$(COMPOSE) down

health:          ## full health report from a worker container
	$(COMPOSE) run --rm --no-deps worker health

render:          ## queue a render on the workers and wait for the PNG (in the `out` volume)
	$(COMPOSE) run --rm --no-deps worker submit --wait

ui-check:        ## the renderer UI answers and serves the VRM
	curl -fsS http://127.0.0.1:$${CLYFFY_RENDERER_PORT:-5273}/healthz && curl -fsSI http://127.0.0.1:$${CLYFFY_RENDERER_PORT:-5273}/clyffy.vrm | head -1

models:          ## optional: download + verify the local TTS models
	$(COMPOSE) --profile tts run --rm fetch-models

tts:             ## optional: speak a line with local OuteTTS (make tts TEXT="hi")
	$(COMPOSE) --profile tts run --rm tts "$(or $(TEXT),We are doing this today.)"

buildx-multiarch: check ## build both arches with buildx (no push; arm64 compiles Blender)
	docker buildx build --platform $(PLATFORMS) --target runtime .
	docker buildx build --platform $(PLATFORMS) --target renderer .

clean-volumes:   ## DANGER: delete the jobs/out/cache/models volumes
	$(COMPOSE) down -v
