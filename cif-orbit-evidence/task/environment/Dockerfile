FROM harbor-claude-code-aggregated:1.3 AS runtime
WORKDIR /workspace
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN python3 -c "import fractions,json,hashlib" \
    && test -s /workspace/materials/structure_alpha.cif \
    && test -s /workspace/materials/structure_beta.cif \
    && test -s /workspace/materials/structure_gamma.cif \
    && test -s /workspace/materials/structure_delta.cif \
    && mkdir -p /workspace/output \
    && chown -R root:0 /workspace/materials \
    && chmod -R a-w /workspace/materials \
    && chmod 1777 /workspace \
    && chown -R 20005:0 /workspace/output
USER 20005
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY skills/ /skills/
