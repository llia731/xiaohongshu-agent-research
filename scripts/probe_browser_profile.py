#!/usr/bin/env python3
"""Public, unauthenticated browser UI check for the specified Xiaohongshu profile.

This intentionally does not bypass login gates, captchas, or access controls.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

PROFILE_URL = "https://www.xiaohongshu.com/user/profile/63572290000000001901d19a"
NOTE_LINK_SELECTORS = 'a[href*="/explore/"], a[href*="/discovery/item/"]'


def probe(screenshot_dir: Path) -> dict:
    from playwright.sync_api import sync_playwright

    screenshot_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target_profile": PROFILE_URL,
        "login_provided": False,
        "mode": "Chrome, real page navigation and at most one UI click",
        "note_texts_are_author_verified": False,
        "post_list_complete": False,
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])
        try:
            context = browser.new_context(viewport={"width": 1365, "height": 900}, locale="zh-CN")
            page = context.new_page()
            try:
                response = page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3500)
                result["navigation_http_status"] = response.status if response else None
                result["profile_url_after_render"] = page.url.split("?")[0]
                result["profile_page_title"] = page.title()[:150]
                result["body_text_length"] = len(page.locator("body").inner_text(timeout=3000))
                result["login_redirected"] = urlparse(page.url).path.startswith("/login")
                result["access_restricted"] = (
                    urlparse(page.url).path.startswith("/website-login/error")
                    or "安全限制" in result["profile_page_title"]
                )
                page.screenshot(path=str(screenshot_dir / "profile.png"), full_page=False)

                links = page.locator(NOTE_LINK_SELECTORS)
                if links.count() == 0 and not result["login_redirected"]:
                    page.mouse.wheel(0, 650)
                    page.wait_for_timeout(1800)
                result["note_anchor_count"] = links.count()
                previews = []
                for i in range(min(links.count(), 8)):
                    item = links.nth(i)
                    href = item.get_attribute("href") or ""
                    previews.append({
                        "url": urljoin(PROFILE_URL, href).split("?")[0],
                        "visible_text": item.inner_text(timeout=2000)[:180],
                    })
                result["note_previews"] = previews
                result["click_attempted"] = False
                if links.count() and not result["login_redirected"]:
                    item = links.first
                    result["click_attempted"] = True
                    result["clicked_note_href"] = urljoin(PROFILE_URL, item.get_attribute("href") or "").split("?")[0]
                    try:
                        item.scroll_into_view_if_needed(timeout=4000)
                        item.click(timeout=8000)
                        page.wait_for_timeout(2700)
                        active = context.pages[-1] if len(context.pages) > 1 else page
                        result["url_after_click"] = active.url.split("?")[0]
                        result["title_after_click"] = active.title()[:150]
                        result["clicked_into_login"] = urlparse(active.url).path.startswith("/login")
                        active.screenshot(path=str(screenshot_dir / "clicked_post.png"), full_page=False)
                    except Exception as exc:
                        result["click_error"] = f"{type(exc).__name__}: {str(exc)[:230]}"
                if result["access_restricted"]:
                    result["outcome"] = "ACCESS_RESTRICTED_BY_PLATFORM"
                elif result["login_redirected"]:
                    result["outcome"] = "LOGIN_REQUIRED_ON_PROFILE"
                elif result["click_attempted"]:
                    result["outcome"] = "POST_CLICK_TESTED" if not result.get("clicked_into_login") else "LOGIN_REQUIRED_ON_POST"
                elif links.count() == 0:
                    result["outcome"] = "PROFILE_LOADED_NO_PUBLIC_POST_ANCHORS"
                else:
                    result["outcome"] = "INDETERMINATE"
            except Exception as exc:
                result["outcome"] = "BROWSER_TEST_ERROR"
                result["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
            finally:
                context.close()
        finally:
            browser.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("browser_probe.json"))
    parser.add_argument("--screenshots-dir", type=Path, default=Path("browser_screenshots"))
    args = parser.parse_args()
    try:
        result = probe(args.screenshots_dir)
    except Exception as exc:
        result = {"outcome": "BROWSER_LAUNCH_ERROR", "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
