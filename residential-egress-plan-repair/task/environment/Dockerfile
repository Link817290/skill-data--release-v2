# Actor environment for both conditions. The no-skill manifest omits the skill
# mount while keeping this image and every source material identical.
FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace

# Install only when the base image does not already provide PDF text extraction.
RUN command -v pdftotext >/dev/null 2>&1 \
 || ( apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils \
 && rm -rf /var/lib/apt/lists/* )

# The wheel ships with the task so actor construction remains offline.
COPY wheels /tmp/wheels

RUN pip install --no-index --find-links=/tmp/wheels --no-cache-dir ezdxf==1.4.4

COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Fail the build if either required source file is absent.
RUN test -s /workspace/residential_floor_plan.dxf \
    && test -s /workspace/fire_safety_code.pdf \
    && mkdir -p /workspace/output

# Harbor archives outputs under the host-side agent uid.
RUN chown -R 20005:0 /workspace
USER 20005

CMD ["/bin/sh"]
