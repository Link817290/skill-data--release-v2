FROM harbor-claude-code-aggregated:1.3 AS runtime

WORKDIR /workspace
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN python3 -c "import csv, json, zipfile, xml.etree.ElementTree" \
    && test -f /workspace/regime_map_template.xlsx \
    && test -f /workspace/market_snapshots.csv \
    && test -f /workspace/output_contract.json
RUN chown -R 20005:0 /workspace
USER 20005
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY skills/ /skills/
