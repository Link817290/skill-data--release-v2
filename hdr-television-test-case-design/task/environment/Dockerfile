FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace
COPY workspace/ /workspace/
COPY skills/ /skills/
RUN python3 -c "import openpyxl" \
    && test -s '/workspace/LG OLED65C22LB.pdf' \
    && test -s /workspace/LG_OLED65C22LB_HDR_Acceptance_Requirements.docx \
    && mkdir -p /workspace/output \
    && chown -R 20005:0 /workspace /skills
USER 20005
