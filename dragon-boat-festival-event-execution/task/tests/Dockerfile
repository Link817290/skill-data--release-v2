ARG VERIFIER_BASE=dragon-boat-festival-event-execution:1.0
FROM ${VERIFIER_BASE}
USER root
COPY . /tests/
RUN chmod -R a+rX /tests && chmod +x /tests/test.sh \
    && mkdir -p /logs/verifier && chmod 0777 /logs/verifier \
    && python3 -c 'import lxml; from pathlib import Path; assert Path("/tests/test.sh").is_file()'
USER 20005
WORKDIR /workspace
