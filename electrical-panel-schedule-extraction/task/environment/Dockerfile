FROM harbor-claude-code-aggregated:1.3 AS runtime
USER root
WORKDIR /workspace
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN test -s /workspace/materials/S-01_电气设计说明.png \
    && test -s /workspace/materials/S-02_配电箱系统图.png \
    && test -s /workspace/materials/S-03_一层电气平面图.png \
    && test -s /workspace/materials/S-04_二层电气平面图.png \
    && mkdir -p /workspace/output \
    && chown -R 20005:0 /workspace
USER 20005
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
USER root
COPY skills/ /skills/
RUN chown -R 20005:0 /skills
USER 20005
