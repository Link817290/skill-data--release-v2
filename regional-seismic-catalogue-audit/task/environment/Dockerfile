FROM harbor-claude-code-aggregated:1.3 AS runtime

USER root
WORKDIR /workspace
COPY --chown=1000:1000 workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN test -s /workspace/materials/catalog_2018_full.html \
    && test -s /workspace/materials/catalog_2018_partial.html \
    && test -s /workspace/materials/catalog_2019_q1_q3.html \
    && mkdir -p /workspace/output \
    && chown -R 1000:1000 /workspace

USER 1000:1000
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY --chown=1000:1000 skills/ /skills/
