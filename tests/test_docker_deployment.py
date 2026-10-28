import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class DockerDeploymentTests(unittest.TestCase):
    def test_private_port_and_persistence(self):
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("127.0.0.1:8501:8501", compose)
        self.assertIn("127.0.0.1:6080:6080", compose)
        self.assertIn("browser_profile:/app/.local", compose)
        self.assertIn("research_outputs:/app/outputs", compose)
        self.assertIn("no-new-privileges:true", compose)
        self.assertNotIn("privileged: true", compose)

    def test_matching_playwright_version(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements-local.txt").read_text(encoding="utf-8")
        self.assertIn("playwright/python:v1.56.0-noble", dockerfile)
        self.assertIn("playwright==1.56.0", requirements)
        self.assertIn("USER pwuser", dockerfile)

    def test_configurable_pypi_mirror(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("ARG PIP_INDEX_URL=", dockerfile)
        self.assertIn('--index-url "${PIP_INDEX_URL}"', dockerfile)
        self.assertIn("mirrors.aliyun.com/pypi/simple/", compose)
        self.assertIn("PIP_INDEX_URL:", compose)

    def test_isolated_python_environment(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("python3.12-venv", dockerfile)
        self.assertIn("python3 -m venv /opt/venv", dockerfile)
        self.assertIn('PATH="/opt/venv/bin:$PATH"', dockerfile)
        self.assertIn("type=cache,target=/root/.cache/pip", dockerfile)
        self.assertIn("python -m pip check", dockerfile)
        self.assertIn("PIP_CACHE_DIR=/root/.cache/pip", dockerfile)
        self.assertIn("ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/", dockerfile)
        self.assertNotIn("--ignore-installed", dockerfile.split("RUN --mount=")[-1].split("COPY . /app")[0])

    def test_gui_services(self):
        entry = (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("Xvfb :99", entry)
        self.assertIn("x11vnc", entry)
        self.assertIn("websockify", entry)
