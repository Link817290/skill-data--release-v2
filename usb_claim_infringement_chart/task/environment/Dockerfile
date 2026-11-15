FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN command -v pdftotext >/dev/null \
    && test -f /workspace/sources/published_application.pdf \
    && test -f /workspace/sources/issued_patent.pdf \
    && test -f /workspace/sources/controller_datasheet.pdf \
    && test -f /workspace/sources/reference_design.pdf \
    && test -f /workspace/sources/product_guide.pdf \
    && test -f /workspace/sources/type_c_specification.pdf \
    && test -f /workspace/sources/power_delivery_specification.pdf \
    && test -f /workspace/analysis_contract.json

CMD ["/bin/sh"]
