FROM harbor-claude-code-aggregated:1.3 AS runtime

USER root
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /workspace/output /logs \
    && chown -R 1000:1000 /workspace /logs
COPY workspace/ /workspace/
WORKDIR /workspace
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN test -s /workspace/materials/hydrology_manuscript.pdf \
    && chown -R 1000:1000 /workspace
USER 1000:1000
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY skills/ /skills/
