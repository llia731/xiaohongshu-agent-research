#!/usr/bin/env python3
"""Read-only environment inspection: no login, no scraping, no credentials."""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import socket
import sys
from pathlib import Path


def diagnose() -> dict:
    checks = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "git_path": shutil.which("git"),
        "node_path": shutil.which("node"),
        "uv_path": shutil.which("uv"),
        "chrome_path": next(
            (p for name in ("chrome", "google-chrome", "chromium", "chromium-browser", "msedge")
             if (p := shutil.which(name))),
            None,
        ),
    }
    dns = {}
    for host in ("github.com", "www.xiaohongshu.com"):
        try:
            dns[host] = {"resolved": True, "addresses": sorted({x[4][0] for x in socket.getaddrinfo(host, 443)})[:5]}
        except OSError as exc:
            dns[host] = {"resolved": False, "error_type": type(exc).__name__}
    checks["dns"] = dns
    checks["message"] = "只检查运行环境和 DNS，不测试登录、账号授权或数据采集。"
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = diagnose()
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
