FROM harbor-claude-code-aggregated:1.3 AS runtime

USER root
RUN mkdir -p /workspace/output /logs \
    && chown -R 1000:1000 /workspace /logs
COPY workspace/ /workspace/
WORKDIR /workspace
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN test -f '/workspace/input/合同条款及报送联系单.docx' \
    && test -f '/workspace/input/第五期付款申报表（空表）.xlsx' \
    && test -f '/workspace/input/第五期计量签认资料.xlsx' \
    && test -f '/workspace/input/资金往来及代扣资料.xlsx' \
    && chown -R 1000:1000 /workspace
USER 1000:1000
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY skills/ /skills/
