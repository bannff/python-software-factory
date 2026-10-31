FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

WORKDIR /work

# The preview SDK bundles libdittoffi. The lock contains hashes for the
# published Linux x86_64 and arm64 wheels; no SDK credential is baked in.
COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes \
        -r /tmp/requirements.lock \
    && python -c "import cbor2, ditto; from PIL import Image; print('edge-lab runtime imports OK:', Image.__version__)" \
    && mkdir -p /work/runs

CMD ["sleep", "infinity"]
