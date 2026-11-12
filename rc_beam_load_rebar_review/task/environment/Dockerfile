FROM harbor-claude-code-aggregated:1.3 AS runtime
WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# Keep the actor image offline-reproducible; pdftotext is supplied by the base
# image and the Python wheel travels with the task.
RUN command -v pdftotext >/dev/null 2>&1 \
 || ( apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils \
 && rm -rf /var/lib/apt/lists/* )
# wheel 随包走，--no-index 保证完全不碰网络。
COPY wheels /tmp/wheels

RUN python3 -m pip install --no-index --find-links=/tmp/wheels --no-cache-dir --break-system-packages openpyxl==3.1.5
COPY workspace /workspace
RUN mkdir -p /logs /app && chown -R 1000:1000 /app /workspace /logs

FROM runtime AS no-skill

FROM runtime AS with-skill
USER root
COPY skills /skills
USER 1000
