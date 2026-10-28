FROM mcr.microsoft.com/playwright/python:v1.56.0-noble

# Browser and Python dependencies remain inside Docker, never on the Ubuntu host.
# Install project packages into an isolated virtualenv, not the system Python.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    HOME=/home/pwuser \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb x11vnc novnc websockify openbox python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-local.txt /app/requirements-local.txt
ARG PIP_INDEX_URL=https://pypi.org/simple

RUN python3 -m venv /opt/venv

# BuildKit cache persists downloaded wheels across failed/repeated image builds.
# No --ignore-installed or --break-system-packages: apt-managed packages remain untouched.
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --disable-pip-version-check \
    --timeout 60 --retries 4 --index-url "${PIP_INDEX_URL}" \
    -r /app/requirements-local.txt \
    && python -m pip check

COPY . /app
RUN mkdir -p /app/.local /app/outputs \
    && chown -R pwuser:pwuser /app /home/pwuser

USER pwuser
EXPOSE 8501 6080
ENTRYPOINT ["bash", "docker/entrypoint.sh"]
