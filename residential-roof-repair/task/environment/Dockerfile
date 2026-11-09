FROM harbor-claude-code-aggregated:1.3 AS runtime

USER root
WORKDIR /workspace
COPY --chown=20005:0 workspace/ /workspace/
RUN mkdir -p /workspace/output && chown -R 20005:0 /workspace
USER 20005
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY --chown=20005:0 skills/ /skills/
