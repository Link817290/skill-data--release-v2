FROM harbor-claude-code-aggregated:1.3 AS runtime

USER root
WORKDIR /workspace
COPY --chown=1000:1000 workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN tar -xzf /workspace/progress-library-release-candidate.tar.gz -C /workspace \
    && test -f /workspace/project/tqdm/std.py \
    && mkdir -p /workspace/output \
    && chown -R 1000:1000 /workspace

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY --chown=1000:1000 skills/ /skills/
