FROM harbor-claude-code-aggregated:1.3 AS runtime
USER root
WORKDIR /workspace
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp/agent-home XDG_CACHE_HOME=/tmp/agent-home/.cache XDG_CONFIG_HOME=/tmp/agent-home/.config
COPY --chown=20005:0 workspace/ /workspace/
RUN python3 -c "import fitz; from pathlib import Path; assert len(list(Path('/workspace/materials').glob('*.pdf')))==3" \
    && mkdir -p /workspace/output /tmp/agent-home/.cache /tmp/agent-home/.config \
    && chown -R 20005:0 /workspace /tmp/agent-home
USER 20005

CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY --chown=20005:0 skills/ /skills/
