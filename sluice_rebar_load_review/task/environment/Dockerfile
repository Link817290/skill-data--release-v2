FROM harbor-claude-code-aggregated:1.3

USER root
WORKDIR /workspace
COPY --chown=20005:0 workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN command -v pdftotext >/dev/null \
    && python3 -c "import openpyxl" \
    && test -s /workspace/materials/full_report_original.pdf \
    && chown -R 20005:0 /workspace
USER 20005
CMD ["/bin/sh"]
