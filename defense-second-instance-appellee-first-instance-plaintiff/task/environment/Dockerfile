FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN test -d /workspace/materials \
    && mkdir -p /workspace/artifacts /workspace/output \
    && chown -R 1000:1000 /workspace
CMD ["/bin/sh"]
