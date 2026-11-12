FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN test -f /workspace/materials/case-001.png \
    && test -f /workspace/materials/case-002.png \
    && test -f /workspace/materials/case-003.png \
    && mkdir -p /workspace/output \
    && chown -R 1000:1000 /workspace
CMD ["/bin/sh"]
