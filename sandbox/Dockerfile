FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends git coreutils \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "pytest>=8,<10" \
    && useradd --uid 10001 --no-create-home sandbox \
    && install -d -o sandbox -g sandbox /workspace
ENV HOME=/workspace TMPDIR=/workspace/.tmp PYTHONDONTWRITEBYTECODE=1
COPY workspace_file.py /usr/local/lib/codeharness/workspace_file.py
USER 10001:10001
WORKDIR /workspace
CMD ["sleep", "infinity"]
