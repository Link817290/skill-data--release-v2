FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace
COPY workspace/ /workspace/
COPY skills/ /skills/
RUN python3 -c "import docx, openpyxl, xlrd" \
    && test -s /workspace/materials/02-01_门店HR复核需求与审查范围.doc \
    && mkdir -p /workspace/output \
    && chown -R 20005:0 /workspace /skills
USER 20005
