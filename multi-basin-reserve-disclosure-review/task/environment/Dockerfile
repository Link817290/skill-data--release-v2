# The evaluation harness probes for its preinstalled command-line agent during setup.
FROM harbor-claude-code-aggregated:1.3 AS runtime

USER root
WORKDIR /workspace
COPY --chown=1000:1000 workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Stop the build if the review package did not copy completely.
RUN test -f /workspace/source_documents/annual_report.html \
    && test -f /workspace/source_documents/earnings_release.html \
    && test "$(find /workspace/source_documents -maxdepth 1 -name '*.html' | wc -l)" = 6 \
    && chmod -R a-w /workspace/source_documents

USER 1000:1000
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY --chown=1000:1000 skills/ /skills/
