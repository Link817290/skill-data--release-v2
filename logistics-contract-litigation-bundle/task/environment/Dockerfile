FROM harbor-claude-code-aggregated:1.3 AS runtime
USER root
WORKDIR /workspace
COPY --chown=20005:0 workspace/ /workspace/
RUN python3 -c "import pathlib; files=[p for p in pathlib.Path('/workspace/materials').iterdir() if p.is_file() and p.stat().st_size>0]; assert len(files)==4" && mkdir -p /workspace/output && chown -R 20005:0 /workspace
USER 20005

CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY --chown=20005:0 skills/ /skills/
