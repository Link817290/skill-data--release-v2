FROM harbor-claude-code-aggregated:1.3 AS runtime

USER root
WORKDIR /workspace
COPY --chown=1000:1000 workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN test -f /workspace/materials/employment_application_record.pdf \
    && test -f /workspace/materials/withholding_record.pdf \
    && test -f /workspace/materials/employment_eligibility_record.pdf \
    && mkdir -p /workspace/output \
    && python3 - <<'PY'
import fitz
import pypdf
print('PyMuPDF', fitz.VersionBind)
PY

RUN chown -R 1000:1000 /workspace
USER 1000:1000
CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY --chown=1000:1000 skills/ /skills/
