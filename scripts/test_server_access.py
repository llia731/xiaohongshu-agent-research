"""Check server HTTP and rendered-browser access without logging in or collecting posts."""
import argparse
import json
import socket
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from scripts.auth_manager import classify_page_state
from scripts.research_core import parse_profile_url

DEFAULT_URL = "https://www.xiaohongshu.com/user/profile/63572290000000001901d19a"


def test_http(url):
    result = {}
    try:
        host = urlparse(url).hostname
        result["dns_resolved"] = bool(socket.getaddrinfo(host, 443))
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=18, context=ssl.create_default_context()) as response:
            result["http_status"] = response.status
            result["final_path"] = urlparse(response.url).path
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    return result


def test_browser(url, directory):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(locale="zh-CN", viewport={"width": 1365, "height": 900})
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2800)
            title = page.title()
            body = page.locator("body").inner_text(timeout=4000)[:15000]
            links = page.locator('a[href*="/explore/"], a[href*="/discovery/item/"]').count()
            assessment = classify_page_state(page.url, title, body, has_note_cards=links > 0)
            page.screenshot(path=str(directory / "browser_page.png"), full_page=False)
            return {
                "state": assessment.state,
                "reason": assessment.reason,
                "http_status": response.status if response else None,
                "final_path": urlparse(page.url).path,
                "page_title": title[:160],
                "visible_note_links": links,
                "screenshot": str(directory / "browser_page.png"),
            }
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-url", default=DEFAULT_URL)
    parser.add_argument("--http-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path(".local/server_probe"))
    args = parser.parse_args()
    url, _ = parse_profile_url(args.profile_url)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "utc_time": datetime.now(timezone.utc).isoformat(),
        "profile": url,
        "logged_in": False,
        "notes_collected": 0,
        "http": test_http(url),
    }
    if not args.http_only:
        try:
            result["browser"] = test_browser(url, args.output_dir)
        except Exception as exc:
            result["browser"] = {"state": "BROWSER_TEST_ERROR", "error_type": type(exc).__name__, "message": str(exc)[:300]}
    (args.output_dir / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("截图和 JSON 保存在服务器本地 .local/server_probe/ 中")


if __name__ == "__main__":
    main()
