# Actor image. Keep the shared runtime skeleton stable; only the dependency
# assertion and the material assertions below are task-specific.
# The aggregated Harbor image already contains the actor runtime and CLI.
#
# The delivery check requires the final runtime to remain on the shared 1.3 image.

FROM harbor-claude-code-aggregated:1.3 AS runtime

WORKDIR /workspace

# Task-specific dependency assertion. The base image normally provides this
# utility; install it only when a local build starts from a thinner image.
RUN command -v pdftotext >/dev/null 2>&1 \
 || ( apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils \
 && rm -rf /var/lib/apt/lists/* )

COPY --chown=20005:0 workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Assert that every supplied manuscript is present in the actor workspace.
# A missing material must fail image construction instead of producing an
# apparently successful rollout against an empty directory.
RUN test -s /workspace/materials/manuscript_early.docx \
    && test -s /workspace/materials/manuscript_current.docx \
    && test -s /workspace/materials/manuscript_alternate.docx \
    && mkdir -p /workspace/output

# Keep the actor uid stable so the host-side archiver can read generated
# artifacts and trajectory JSONL files.
RUN chown -R 20005:0 /workspace
USER 20005

CMD ["/bin/sh"]

FROM runtime AS no-skill

FROM runtime AS with-skill
COPY --chown=20005:0 skills/ /skills/
