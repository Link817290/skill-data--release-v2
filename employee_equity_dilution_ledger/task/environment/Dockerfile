FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace
# Skip package installation when the base image already provides pdftotext;
# this keeps the actor image build reproducible in an offline environment.
RUN command -v pdftotext >/dev/null 2>&1 \
 || ( apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils \
 && rm -rf /var/lib/apt/lists/* )
COPY workspace/ /workspace/
COPY compat/apk /usr/local/sbin/apk
COPY compat/npm /usr/local/sbin/npm
RUN chmod 0755 /usr/local/sbin/apk /usr/local/sbin/npm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN test -f /workspace/materials/annual_report.pdf \
    && test -f /workspace/materials/proxy_statement.html \
    && python3 -c "import openpyxl, lxml" \
    && chown -R 20005:0 /workspace

USER 20005
CMD ["/bin/sh"]
