FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN test -d /workspace/materials \
    && test "$(find /workspace/materials -maxdepth 1 -type f | wc -l)" = 14 \
    && python3 -c "import openpyxl; assert openpyxl.__version__ == '3.1.5'" \
    && mkdir -p /workspace/output \
    && chown -R 20005:0 /workspace

USER 20005
CMD ["/bin/sh"]
