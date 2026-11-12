# The base image must carry its tag. Without one docker appends :latest and tries to
# pull from the internet, which the evaluation machines cannot reach, and the build
# fails with a timeout that reads like a network fault.
FROM harbor-claude-code-aggregated:1.3

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Only workspace/ is copied. Copying skills/ as well bakes it into the image, so the
# no-skill condition could still read it inside the container and the two conditions
# would stop being mutually exclusive. skills/ stays outside the build context and the
# harness decides whether to mount it, per task.toml / task_no_skill.toml.
WORKDIR /app/environment
RUN mkdir -p /app/environment /logs /workspace/output
COPY task/environment/workspace/ /workspace/
RUN ln -s /workspace/materials /app/environment/materials \
    && ln -s /workspace/output /app/environment/output \
    && chown -R 1000:1000 /app /logs /workspace

# Build-time self check: a workspace that failed to copy is a silent failure, and the
# run comes out as an empty turn rather than an error.
RUN test -s "/workspace/materials/招聘岗位要求.docx" \
    && test -s "/workspace/materials/附件1公开招聘岗位明细表.xlsx"

CMD ["/bin/sh"]
