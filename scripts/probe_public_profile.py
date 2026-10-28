#!/usr/bin/env python3
"""Single unauthenticated URL reachability test; does not download or save post content."""
from __future__ import annotations

import argparse
import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.xiaohongshu.com/user/profile/63572290000000001901d19a"


def probe() -> dict:
    info = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "url_without_token": URL,
        "authenticated": False,
        "attempts": 1,
        "purpose": "Check public URL connectivity only; does not fetch post lists",
    }
    request = urllib.request.Request(URL, headers={"User-Agent": "KnowledgeResearchConnectivityCheck/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=12, context=ssl.create_default_context()) as response:
            info.update({
                "http_status": response.status,
                "final_url": response.url.split("?")[0],
                "response_content_type": response.headers.get("Content-Type", ""),
                "can_retrieve_posts": "unverified",
            })
    except urllib.error.HTTPError as exc:
        info.update({"http_status": exc.code, "error": "HTTP response; access not verified"})
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        info.update({"http_status": None, "error_type": type(exc).__name__, "error": str(exc)[:200]})
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("public_profile_probe.json"))
    args = parser.parse_args()
    result = probe()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
