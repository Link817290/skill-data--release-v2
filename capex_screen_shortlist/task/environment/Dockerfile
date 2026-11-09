FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Fail the build loudly rather than shipping an image whose workspace silently
# did not copy: a missing COPY here produces an empty run, not an error.
RUN test -f /workspace/shortlist_template.xlsx \
    && test -f /workspace/candidate_universe.csv \
    && test -f /workspace/methodology/capex-screen-framework.png \
    && test "$(find /workspace/structured-data/provider-snapshots -name '*.json' | wc -l)" = 60

CMD ["/bin/sh"]
