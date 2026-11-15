FROM harbor-claude-code-aggregated:1.3
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates libfontconfig1 libx11-6 libxcursor1 libxinerama1 libxi6 libxrandr2 libasound2 libgl1 libgl1-mesa-dri xvfb xauth && rm -rf /var/lib/apt/lists/*
RUN curl -fL https://github.com/godotengine/godot-builds/releases/download/4.4.1-stable/Godot_v4.4.1-stable_linux.x86_64.zip -o /tmp/godot.zip && echo "ef4e76880a514257175544952c61191106fdef3095b909bafed9fcbeb230c3e5533920a0f3012882dd4bbde83028a67549825794e2d2c3cf76eba7918b71370e  /tmp/godot.zip" | sha512sum -c - && unzip /tmp/godot.zip -d /opt/godot && mv /opt/godot/Godot_v4.4.1-stable_linux.x86_64 /usr/local/bin/godot && chmod +x /usr/local/bin/godot && rm /tmp/godot.zip
WORKDIR /workspace
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt
# The complete verifier runtime is delivered in this build context. The same
# files are available to independent image builders and copied into /opt.
COPY build-context/runtime/ /opt/fx-tools/
COPY workspace/ /workspace/
ENV FX_TOOLS=/opt/fx-tools
ENV PYTHONDONTWRITEBYTECODE=1
RUN mkdir -p /workspace/output /logs/verifier /logs/artifacts && chown -R 20005:0 /workspace /logs && chmod -R a+rX /opt/fx-tools
USER 20005
CMD ["sh"]
