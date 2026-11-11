FROM harbor-claude-code-aggregated:1.3

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app/environment
RUN mkdir -p /app/environment /logs /workspace/output
COPY workspace/ /workspace/
RUN ln -s /workspace/materials /app/environment/materials \
    && ln -s /workspace/output /app/environment/output \
    && chown -R 1000:1000 /app /logs /workspace

# The draft has to build from the supplied sources before any revision of it can
# be judged. Failing here at build time is preferable to discovering mid-run
# that the toolchain cannot produce the artifact the task asks for.
RUN set -e; cd /tmp; unzip -q /workspace/materials/D2D_conf.zip; cd D2D_conf; \
    rm -f *.pdf; \
    pdflatex -interaction=nonstopmode -shell-escape D2D_resource_allocation_conf.tex >/dev/null 2>&1 || true; \
    pdflatex -interaction=nonstopmode -shell-escape D2D_resource_allocation_conf.tex >/dev/null 2>&1 || true; \
    test -s D2D_resource_allocation_conf.pdf; \
    pages="$(pdfinfo D2D_resource_allocation_conf.pdf | sed -n 's/^Pages:[[:space:]]*//p')"; \
    test "$pages" -ge 5; \
    rm -rf /tmp/D2D_conf

CMD ["/bin/sh"]
