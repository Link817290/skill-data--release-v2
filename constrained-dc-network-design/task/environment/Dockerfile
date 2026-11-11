# Harbor probes the base image for its preinstalled agent CLI during setup.
FROM harbor-claude-code-aggregated:1.3

WORKDIR /workspace
RUN ln -sf /usr/bin/python3 /usr/local/bin/python
# wheel 随包走，--no-index 保证完全不碰网络。
COPY wheels /tmp/wheels

RUN python3 -m pip install --no-index --find-links=/tmp/wheels --no-cache-dir openpyxl==3.1.5 pulp==3.3.0

# Harbor's installed-agent hook invokes the online bootstrap even though this
# required base image already contains Claude Code. Keep that probe offline-safe
# while leaving every unrelated curl request unchanged.
RUN mv /usr/bin/curl /usr/bin/curl.real \
    && printf '%s\n' '#!/bin/sh' 'case "$*" in' '*downloads.claude.ai*) printf "#!/bin/sh\\nexit 0\\n" ;;' '*) exec /usr/bin/curl.real "$@" ;;' 'esac' > /usr/local/bin/curl \
    && chmod +x /usr/local/bin/curl
COPY workspace/ /workspace/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN test -f "/workspace/Supply chain logisitcs problem.xlsx"

CMD ["/bin/sh"]
