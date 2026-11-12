FROM harbor-claude-code-aggregated:1.3 AS runtime

USER root
WORKDIR /workspace
COPY workspace/ /workspace/
RUN test -s /workspace/materials/03_原始材料.xlsx \
    && test -s /workspace/templates/review_report_template.md \
    && echo "b2f77b725afbe9751721af8016e2a1fb2ca07999084c2e499435bcb2e59c9185  /workspace/materials/03_原始材料.xlsx" | sha256sum -c - \
    && mkdir -p /workspace/output /logs \
    && chown -R 20005:0 /workspace /logs
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 20005
CMD ["sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
USER root
COPY skills/ /skills/
RUN chown -R 20005:0 /skills
USER 20005
