FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace

COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 NODE_OPTIONS="--max-old-space-size=256"

RUN test -s "/workspace/materials/2024年客诉月CPPM统计表.xlsx" \
    && test -s "/workspace/materials/output_contract.json" \
    && mkdir -p /workspace/output \
    && chown -R 20005:0 /workspace

USER 20005
