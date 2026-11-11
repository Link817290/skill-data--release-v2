FROM harbor-claude-code-aggregated:1.3 AS runtime
USER root
WORKDIR /workspace
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN test -s /workspace/materials/每日供需.csv \
    && test -s /workspace/materials/機組發電.json \
    && mkdir -p /workspace/output \
    && chown -R 20005:0 /workspace /home/agent
USER 20005
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
USER root
COPY skills/ /skills/
RUN chown -R 20005:0 /skills
USER 20005
