FROM harbor-claude-code-aggregated:1.3

USER root
COPY --chown=20005:20005 workspace/ /workspace/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 20005
WORKDIR /workspace
CMD ["/bin/sh"]
