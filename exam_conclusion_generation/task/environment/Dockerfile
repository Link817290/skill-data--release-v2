FROM harbor-claude-code-aggregated:1.3 AS runtime
USER root
WORKDIR /workspace
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN test -s /workspace/匿名体检检查明细.xlsx \
    && test -s /workspace/体检总检结论_填写模板.xlsx \
    && chown -R 20005:0 /workspace
USER 20005
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
USER root
COPY skills/ /skills/
RUN chown -R 20005:0 /skills
USER 20005
