# Reproducible environment for VFRED-Gate on Linux.
#   docker build -t vfred-gate .
#   docker run --rm -v "$PWD/models:/models:ro" -v "$PWD/runs:/work/runs" -v vfg-cache:/cache \
#     vfred-gate compare --model /models/m.gguf --b-cflags "-ffp-contract=fast"
FROM python:3.12-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends cmake ninja-build g++ git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY . .
RUN pip install --no-cache-dir . && rm -rf /src
ENV VFG_CACHE=/cache
VOLUME /cache
WORKDIR /work
ENTRYPOINT ["vfg"]
CMD ["--help"]
