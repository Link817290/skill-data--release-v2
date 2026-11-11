FROM harbor-claude-code-aggregated:1.3
USER root
WORKDIR /workspace
COPY --chown=20005:20005 workspace/ /workspace/
COPY --chown=20005:20005 skills/ /skills/
RUN install -d -o 20005 -g 0 -m 755 /home/agent /home/agent/.cache /home/agent/.config /home/agent/.local /home/agent/.local/share \
    && install -d -o 20005 -g 0 -m 700 /home/agent/.cache/dconf \
    && mkdir -p /workspace/output \
    && chown 20005:20005 /workspace/output \
    && python3 -c "import openpyxl, uno" \
    && libreoffice --version \
    && chown -R 20005:0 /home/agent/.cache /home/agent/.config /home/agent/.local
USER 20005
