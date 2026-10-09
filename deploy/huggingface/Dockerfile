FROM ollama/ollama:0.6.8@sha256:50ab2378567a62b811a2967759dd91f254864c3495cbe50576bd8a85bc6edd56 AS ollama

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=7860 \
    NOOR_OLLAMA_ENABLED=true NOOR_OLLAMA_MODEL=qwen2.5:1.5b \
    OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS=/home/noor/.ollama/models \
    OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=30m
RUN useradd --create-home --uid 1000 noor \
    && install -d -o 1000 -g 1000 /home/noor/.ollama
WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=secret,id=build_ca_bundle \
    if [ -f /run/secrets/build_ca_bundle ]; then export PIP_CERT=/run/secrets/build_ca_bundle; fi; \
    pip install --no-cache-dir --require-hashes -r requirements.txt
# The CPU libraries are sufficient for the default CPU Space; omit CUDA layers.
COPY --from=ollama /bin/ollama /usr/bin/ollama
COPY --from=ollama /usr/lib/ollama/*.so /usr/lib/ollama/
COPY --chown=1000:1000 app ./app
COPY --chown=1000:1000 data ./data
COPY --chown=1000:1000 scripts/cloud_start.py scripts/pull_cloud_model.py ./scripts/
COPY --chown=1000:1000 LICENSE ./LICENSE
COPY --chown=1000:1000 deploy/licenses ./runtime-licenses
USER noor
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','7860')+'/api/health',timeout=3)"
CMD ["python", "scripts/cloud_start.py"]
