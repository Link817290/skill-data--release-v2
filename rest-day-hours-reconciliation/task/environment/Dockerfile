FROM harbor-claude-code-aggregated:1.3 AS runtime

USER root
WORKDIR /workspace
COPY --chown=1000:1000 workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp/agent-home XDG_CACHE_HOME=/tmp/agent-home/.cache XDG_CONFIG_HOME=/tmp/agent-home/.config
RUN test -f /workspace/materials/01_门店排班版本记录.xlsx \
    && test -f /workspace/materials/07_集团工时与调休管理办法节选.txt \
    && mkdir -p /workspace/output /tmp/agent-home/.cache /tmp/agent-home/.config \
    && chown -R 1000:1000 /workspace /tmp/agent-home
USER 1000

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY --chown=1000:1000 skills/ /skills/

FROM runtime
CMD ["/bin/sh"]
