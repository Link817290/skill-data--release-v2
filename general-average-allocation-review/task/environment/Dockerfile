FROM harbor-claude-code-aggregated:1.3 AS runtime

USER root
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && install -d -o 1000 -g 1000 /workspace /workspace/deliverables
COPY --chown=1000:1000 workspace/ /workspace/
WORKDIR /workspace
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN test -f /workspace/general_average_adjustment.pdf \
    && test -f /workspace/final_judgment.pdf \
    && test -f /workspace/first_instance_judgment.pdf \
    && test -f /workspace/court_of_appeal_judgment.pdf \
    && test "$(pdfinfo /workspace/general_average_adjustment.pdf | awk '/^Pages:/ {print $2}')" = 95 \
    && test "$(pdfinfo /workspace/final_judgment.pdf | awk '/^Pages:/ {print $2}')" = 48 \
    && test "$(pdfinfo /workspace/first_instance_judgment.pdf | awk '/^Pages:/ {print $2}')" = 32 \
    && test "$(pdfinfo /workspace/court_of_appeal_judgment.pdf | awk '/^Pages:/ {print $2}')" = 28 \
    && chown -R 1000:1000 /workspace

USER 1000:1000
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY --chown=1000:1000 skills/ /skills/
