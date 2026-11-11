FROM harbor-claude-code-aggregated:1.3 AS runtime

USER root
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils unzip \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /workspace /logs \
    && chown -R 1000:1000 /workspace /logs
COPY workspace/ /workspace/
WORKDIR /workspace
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN test -f /workspace/review_template.json \
    && test -f /workspace/data/review_transactions.csv \
    && test -f /workspace/data/candidate_list_records.csv \
    && test -f /workspace/source_documents/financial-crime-advisory.txt \
    && test -f /workspace/source_documents/vnesheconombank-group-non-financial-report-2015.pdf \
    && test "$(find /workspace/source_documents -type f | wc -l)" -ge 10 \
    && chown -R 1000:1000 /workspace
USER 1000:1000
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY skills/ /skills/
