# Harbor probes this image for a preinstalled Claude Code CLI during setup.
FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN test -f /workspace/01_staff_comment.pdf \
    && test -f /workspace/02_company_response.htm \
    && test -f /workspace/03_amended_registration_statement.htm \
    && test -f /workspace/04_issued_filing.htm \
    && test -f /workspace/05_remediation_annual_report.pdf \
    && test -f /workspace/06_estimate_change_annual_report.pdf \
    && test -f /workspace/review_template.csv

CMD ["/bin/sh"]
