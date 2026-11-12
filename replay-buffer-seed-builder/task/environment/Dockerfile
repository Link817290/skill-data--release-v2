# The base image must be pinned. Without a tag docker appends :latest and tries
# to pull from the public internet, which the evaluation machines cannot reach;
# the build then fails as a timeout that looks like a network fault.
FROM harbor-claude-code-aggregated:1.3
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# The qualified 1.3 base supplies Python and NumPy. Verify the runtime rather
# than downloading dependencies during an offline build.
RUN python3 -c "import numpy; assert tuple(map(int, numpy.__version__.split('.')[:2])) >= (2, 0)"

# Copy workspace/ only. The build context is environment/, so `COPY . ` would
# bake environment/skills/ into the image and the no-skill container could read
# the skill even without mounting it, which destroys the exclusivity of the two
# conditions. skills/ stays out of the image; the harness decides whether to
# mount it from task.toml or task_no_skill.toml.
WORKDIR /app/environment
RUN mkdir -p /app/environment /logs /workspace/output
COPY workspace/ /workspace/
RUN ln -s /workspace/materials /app/environment/materials \
    && ln -s /workspace/output /app/environment/output \
    && chown -R 1000:1000 /app /logs /workspace

# Build-time self check. A workspace that failed to copy is a silent failure:
# the run comes out empty instead of erroring. The .npz must also actually open
# under numpy, otherwise the file is present but the scorer never gets any data.
RUN test -s "/workspace/materials/trajectory_unified.npz" \
    && test -s "/workspace/materials/grasp_phase_segments.json" \
    && test -s "/workspace/materials/ppo_script.py" \
    && python3 -c "import numpy; a = numpy.load('/workspace/materials/trajectory_unified.npz'); assert a['qpos'].ndim == 2"

CMD ["/bin/sh"]
