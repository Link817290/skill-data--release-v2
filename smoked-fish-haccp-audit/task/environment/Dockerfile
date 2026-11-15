FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN test -s /workspace/review_dossier.pdf \
    && test -s /workspace/applicable_regulatory_authority.pdf \
    && pdfinfo /workspace/review_dossier.pdf >/dev/null \
    && pdfinfo /workspace/applicable_regulatory_authority.pdf >/dev/null

CMD ["/bin/sh"]
