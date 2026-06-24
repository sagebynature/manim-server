FROM manimcommunity/manim:v0.20.1

USER root
WORKDIR /app

ENV HOST=0.0.0.0 \
    PORT=8000 \
    DATA_DIR=/data \
    TEMPLATE_DIR=/template \
    MANIM_CLI_FLAGS=-ql \
    MANIM_TIMEOUT_SECONDS=120 \
    PATH=/opt/venv/bin:/usr/local/texlive/bin/aarch64-linux:/usr/local/texlive/bin/x86_64-linux:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin

COPY pyproject.toml uv.lock ./
RUN python -m pip install --no-cache-dir uv

COPY app ./app
COPY template /template
RUN uv pip install --no-cache .

RUN mkdir -p /data /template && chown -R manimuser:manimuser /data /template /app

USER manimuser
EXPOSE 8000
VOLUME ["/data", "/template"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import json, urllib.request; json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2))['ok']"

CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST} --port ${PORT}"]
