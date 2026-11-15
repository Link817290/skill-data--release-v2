FROM harbor-claude-code-aggregated:1.3 AS runtime

USER root
WORKDIR /workspace
COPY --chown=1000:1000 workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN test -f /workspace/faers/demo.csv \
    && test -f /workspace/faers/drug.csv \
    && test -f /workspace/faers/reac.csv \
    && test -f /workspace/faers/ther.csv \
    && test -f /workspace/faers/outc.csv \
    && test -f /workspace/faers_readme.txt \
    && mkdir -p /workspace/output \
    && chown -R 1000:1000 /workspace

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY --chown=1000:1000 skills/ /skills/
