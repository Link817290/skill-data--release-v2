FROM harbor-claude-code-aggregated:1.3
USER root
COPY requirements.txt /tmp/task-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/task-requirements.txt
COPY --chown=20005:20005 workspace/ /workspace/
USER 20005
WORKDIR /workspace
