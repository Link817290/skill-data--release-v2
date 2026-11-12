FROM harbor-claude-code-aggregated:1.3 AS runtime
USER root
WORKDIR /workspace
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp/agent-home XDG_CACHE_HOME=/tmp/agent-home/.cache XDG_CONFIG_HOME=/tmp/agent-home/.config
COPY workspace/ /workspace/
RUN python3 -c "from pathlib import Path; p=Path('/workspace/materials'); assert len(list(p.glob('*.pdf')))==2; assert (p/'case-background.md').stat().st_size>0" \
    && mkdir -p /workspace/output /tmp/agent-home/.cache /tmp/agent-home/.config \
    && chown -R 20005:0 /workspace /tmp/agent-home
USER 20005
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
USER root
COPY skills/ /skills/
RUN chown -R 20005:0 /skills
USER 20005
