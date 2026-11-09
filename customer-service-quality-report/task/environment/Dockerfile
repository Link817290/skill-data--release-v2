FROM harbor-claude-code-aggregated:1.3
WORKDIR /workspace
COPY workspace/ /workspace/
RUN python3 -c "import openpyxl, pathlib; assert len(list(pathlib.Path('/workspace/materials').glob('*.xlsx'))) == 2" \
    && command -v libreoffice >/dev/null \
    && mkdir -p /workspace/output && chown -R 20005:0 /workspace
USER 20005
