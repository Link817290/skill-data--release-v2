FROM node:22.23.0-bookworm-slim AS node_runtime
FROM harbor-claude-code-aggregated:1.3 AS runtime
USER root
COPY --from=node_runtime /usr/local/ /opt/node22/
ENV PATH=/opt/node22/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends chromium fonts-noto-cjk ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/remotion-runtime
COPY workspace/project/package.json workspace/project/package-lock.json ./
RUN env -u HTTPS_PROXY -u HTTP_PROXY -u ALL_PROXY -u https_proxy -u http_proxy -u all_proxy npm ci --cache /opt/npm-cache --no-audit --no-fund
COPY workspace/ /workspace/
ENV CHROME_PATH=/usr/bin/chromium NODE_PATH=/opt/remotion-runtime/node_modules npm_config_cache=/opt/npm-cache
RUN ln -s /opt/remotion-runtime/node_modules /workspace/node_modules && mkdir -p /workspace/output /logs/verifier /logs/artifacts && chown -R 20005:0 /workspace /logs /opt/npm-cache
WORKDIR /workspace
USER 20005
CMD ["bash"]
FROM runtime AS no-skill
FROM runtime AS with-skill
COPY skills/ /skills/
