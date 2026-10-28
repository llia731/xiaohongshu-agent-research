#!/usr/bin/env python3
"""Manual QR authorization within ONE GitHub Actions job.

Only for a private repository and explicitly user-triggered runs.
Never saves cookies, browser state or credentials as artifacts.
Stops on a platform access restriction; no automated CAPTCHA handling.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

PROFILE = "https://www.xiaohongshu.com/user/profile/63572290000000001901d19a"
HOME = "https://www.xiaohongshu.com"
TERMINAL = {
    "ACCESS_RESTRICTED", "QR_UNAVAILABLE", "LOGIN_EXPIRED",
    "AUTHENTICATED", "BROWSER_ERROR", "AUTHENTICATED_PROFILE_UNAVAILABLE",
}


def publish(directory: Path, state: str, **metadata: object) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    obj = {
        "state": state,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "auth_method": "qrcode",
        "session_persisted": False,
        **metadata,
    }
    tmp = directory / "status.json.tmp"
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(directory / "status.json")


def is_access_restricted(page) -> bool:
    return urlparse(page.url).path.startswith("/website-login/error") or "安全限制" in page.title()


def qr_locator(page):
    candidates = [
        "img.qrcode-img",
        ".qrcode img",
        'img[alt*="二维码"]',
        'img[alt*="扫码"]',
    ]
    for css in candidates:
        locator = page.locator(css)
        if locator.count() and locator.first.is_visible():
            return locator.first
    return None


def show_login_if_needed(page) -> None:
    if qr_locator(page) is not None:
        return
    for selector in ['button:has-text("登录")', 'text="二维码登录"', 'text="扫码登录"']:
        locator = page.locator(selector)
        try:
            if locator.count() and locator.first.is_visible():
                locator.first.click(timeout=2500)
                page.wait_for_timeout(700)
                if qr_locator(page) is not None:
                    return
        except Exception:
            continue


def is_logged_in(page, context, original_web_session: str | None) -> bool:
    try:
        # Site's normal signed-in navigation is preferred to cookie-only inference.
        if page.locator('a[href*="/user/profile/"] span:text-is("我")').count():
            return True
        cookies = context.cookies(HOME)
        current = next((c.get("value") for c in cookies if c.get("name") == "web_session"), None)
        return bool(current and current != original_web_session)
    except Exception:
        return False


def collect_visible_cards(page, directory: Path) -> int:
    from scripts.hosted_browser_research import canonical_note_url
    from scripts.hosted_browser_research import classify_state

    page.goto(PROFILE, wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(1600)
    if classify_state(page.url, page.title(), page.locator("body").inner_text(timeout=4000)[:10000]) in (
        "ACCESS_RESTRICTED", "AUTH_REQUIRED"
    ):
        return -1

    collected = {}
    links = page.locator('a[href*="/explore/"], a[href*="/discovery/item/"]')
    for i in range(min(links.count(), 40)):
        item = links.nth(i)
        try:
            link = canonical_note_url(item.get_attribute("href") or "")
            if link and link not in collected:
                content = item.inner_text(timeout=1200).strip()
                collected[link] = {
                    "note_id": link.rsplit("/", 1)[-1],
                    "note_url": link,
                    "title": content.splitlines()[0][:160] if content else "",
                    "source": "authorized_ui_card",
                    "content_complete": False,
                }
            if len(collected) >= 10:
                break
        except Exception:
            continue
    with (directory / "visible_cards.jsonl").open("w", encoding="utf-8") as file:
        for card in collected.values():
            file.write(json.dumps(card, ensure_ascii=False) + "\n")
    return len(collected)


def run(output: Path, timeout_seconds: int) -> None:
    from playwright.sync_api import sync_playwright

    publish(output, "STARTING")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN")
            page = context.new_page()
            page.goto(HOME, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(1000)
            if is_access_restricted(page):
                publish(output, "ACCESS_RESTRICTED", reason="小红书返回安全限制页面，停止自动操作")
                return
            original = next((c.get("value") for c in context.cookies(HOME) if c.get("name") == "web_session"), None)
            show_login_if_needed(page)
            qr = qr_locator(page)
            if qr is None:
                publish(output, "QR_UNAVAILABLE", reason="在正常登录界面找不到可见二维码")
                return
            # Only the QR image is uploaded. It is a time-sensitive authentication challenge.
            qr.screenshot(path=str(output / "scan_me.png"), timeout=5000)
            publish(output, "QR_READY", reason="请在私有仓库 Actions 运行页下载二维码并扫码")
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                if is_access_restricted(page):
                    publish(output, "ACCESS_RESTRICTED", reason="扫码期间出现安全限制")
                    return
                if is_logged_in(page, context, original):
                    try:
                        count = collect_visible_cards(page, output)
                        if count == -1:
                            publish(output, "AUTHENTICATED_PROFILE_UNAVAILABLE",
                                    reason="完成扫码，但目标主页仍要求授权或访问受限")
                        else:
                            publish(output, "AUTHENTICATED", visible_card_count=count,
                                    reason="扫码完成；卡片仅用于访问能力验证，未生成完整帖子")
                    except Exception as exc:
                        publish(output, "AUTHENTICATED_PROFILE_UNAVAILABLE", error_type=type(exc).__name__)
                    return
                time.sleep(1)
            publish(output, "LOGIN_EXPIRED", reason="等待扫码超时；本次运行不再重试")
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/qr"))
    parser.add_argument("--timeout-seconds", type=int, default=150)
    args = parser.parse_args()
    if not 30 <= args.timeout_seconds <= 180:
        parser.error("timeout must be 30–180 seconds")
    try:
        run(args.output_dir, args.timeout_seconds)
    except Exception as exc:
        publish(args.output_dir, "BROWSER_ERROR", error_type=type(exc).__name__)


if __name__ == "__main__":
    main()
