FROM harbor-claude-code-aggregated:1.3
USER root
WORKDIR /workspace
COPY workspace/ /workspace/
RUN command -v libreoffice >/dev/null \
    && python3 -c "import openpyxl; assert openpyxl.__version__ == '3.1.5'" \
    && chown -R agent:agent /workspace
ENV HOME=/home/agent
