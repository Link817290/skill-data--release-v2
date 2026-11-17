FROM harbor-claude-code-aggregated:1.3
WORKDIR /workspace
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp/agent-home XDG_CACHE_HOME=/tmp/agent-home/.cache XDG_CONFIG_HOME=/tmp/agent-home/.config
COPY workspace/ /workspace/
COPY wheels/ /tmp/task-wheels/
RUN python3 -m pip install --no-index --find-links=/tmp/task-wheels python-docx==1.2.0 --break-system-packages \
    && python3 -c "import docx; from pathlib import Path; assert len(list(Path('/workspace/materials').glob('*.docx')))==5" \
    && mkdir -p /workspace/output /tmp/agent-home/.cache /tmp/agent-home/.config \
    && chown -R 20005:0 /workspace /tmp/agent-home
USER 20005
