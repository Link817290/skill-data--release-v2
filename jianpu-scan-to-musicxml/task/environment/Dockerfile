FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace
COPY workspace/ /workspace/
COPY skills/ /skills/
RUN test -s /workspace/materials/source_page_01.png \
    && test -s /workspace/materials/source_page_02.png \
    && mkdir -p /workspace/output \
    && chown -R 20005:0 /workspace /skills
USER 20005
