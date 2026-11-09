FROM harbor-claude-code-aggregated:1.3 AS runtime
USER root
WORKDIR /workspace
RUN python3 -c "import sys,numpy,scipy; assert sys.version_info[:2]==(3,11); assert numpy.__version__=='2.2.6'; assert scipy.__version__=='1.13.1'"
COPY workspace/ /workspace/
COPY source_hashes.json /tmp/calibration-source-hashes.json
RUN python3 -c "import hashlib,json; from pathlib import Path; hashes=json.loads(Path('/tmp/calibration-source-hashes.json').read_text()); assert hashes and all(hashlib.sha256((Path('/workspace')/p).read_bytes()).hexdigest()==h for p,h in hashes.items())" \
    && mkdir -p /workspace/output /logs \
    && chown -R 20005:0 /workspace /logs
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
USER 20005
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY skills/ /skills/
