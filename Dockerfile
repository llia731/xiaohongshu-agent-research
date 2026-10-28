FROM mcr.microsoft.com/playwright/python:v1.56.0-noble
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DISPLAY=:99 HOME=/home/pwuser
RUN apt-get update && apt-get install -y --no-install-recommends xvfb x11vnc novnc websockify openbox && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-local.txt /app/requirements-local.txt
# Build-time mirror; select a reachable trusted PyPI index per deployment environment.
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN python -m pip install --disable-pip-version-check --no-cache-dir \
    --timeout 60 --retries 4 --index-url "${PIP_INDEX_URL}" \
    -r /app/requirements-local.txt
COPY . /app
RUN mkdir -p /app/.local /app/outputs && chown -R pwuser:pwuser /app /home/pwuser
USER pwuser
EXPOSE 8501 6080
ENTRYPOINT ["bash", "docker/entrypoint.sh"]
