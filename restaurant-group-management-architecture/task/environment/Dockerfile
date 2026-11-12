FROM harbor-claude-code-aggregated:1.3

ENV DEBIAN_FRONTEND=noninteractive

RUN mkdir -p /app /logs /workspace \
    && ln -s /workspace /app/environment
COPY workspace/ /workspace/

RUN chown -R 1000:1000 /app /logs /workspace

WORKDIR /app/environment
CMD ["/bin/sh"]
