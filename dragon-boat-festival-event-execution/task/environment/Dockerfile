FROM harbor-claude-code-aggregated:1.3
COPY workspace/ /workspace/
RUN python3 -c 'import docx, openpyxl, lxml, PIL; from pathlib import Path; assert Path("/workspace/materials/event-proposal.docx").is_file(); assert Path("/workspace/materials/materials-checklist.xlsx").is_file()' \
    && chown -R 20005:0 /workspace
USER 20005
WORKDIR /workspace
