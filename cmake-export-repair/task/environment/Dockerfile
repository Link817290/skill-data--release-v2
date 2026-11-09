FROM harbor-claude-code-preinstalled:2.1.258-20260902

ENV LANG=C
ENV LC_ALL=C

RUN command -v cmake && command -v gcc && command -v make \
    && command -v git && command -v patch && command -v pkg-config
COPY wheels/ /opt/wheels/
RUN python3 -m pip install --break-system-packages --no-cache-dir --no-index \
    --find-links=/opt/wheels pytest==8.4.1 unidiff==0.7.5 \
    && rm -rf /opt/wheels

WORKDIR /workspace
COPY workspace/ /workspace/
