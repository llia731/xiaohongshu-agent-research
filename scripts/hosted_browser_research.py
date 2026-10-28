#!/usr/bin/env python3
"""Small, unauthenticated browser UI check. Stop on login or security gates."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin

URL = "https://www.xiaohongshu.com/user/profile/63572290000000001901d19a"
SELECTOR = 'a[href*="/explore/"], a[href*="/discovery/item/"]'


def classify_state(url, title, body):
    path = urlparse(url).path
    if path.startswith("/website-login/error") or "安全限制" in title or "请通过安全验证" in body:
        return "ACCESS_RESTRICTED"
    if path == "/login" or path.startswith("/login/") or path.startswith("/website-login/login"):
        return "AUTH_REQUIRED"
    if "登录即可查看" in body or "登录后查看更多" in body:
        return "LOGIN_PROMPT"
    return "VISIBLE"


def canonical_note_url(href):
    parsed = urlparse(urljoin(URL, href))
    if parsed.scheme != "https" or parsed.hostname != "www.xiaohongshu.com":
        return None
    match = re.fullmatch(r"/(?:explore|discovery/item)/([0-9a-fA-F]{12,32})/?", parsed.path)
    return f"https://www.xiaohongshu.com/explore/{match.group(1)}" if match else None


def inspect(mode, output, maximum):
    from playwright.sync_api import sync_playwright
    report = {
        "utc_time": datetime.now(timezone.utc).isoformat(),
        "profile": URL, "mode": mode, "authenticated": False,
        "content_complete": False, "post_details_collected": 0,
    }
    cards = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        try:
            context = browser.new_context(viewport={"width": 1365, "height": 900}, locale="zh-CN")
            page = context.new_page()
            try:
                response = page.goto(URL, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2400)
                title = page.title()[:100]
                body = page.locator("body").inner_text(timeout=4000)[:10000]
                state = classify_state(page.url, title, body)
                report.update({"http_status": response.status if response else None,
                               "page_state": state, "final_path": urlparse(page.url).path,
                               "page_title": title})
                page.screenshot(path=str(output / "profile.png"), full_page=False)
                if state in ("ACCESS_RESTRICTED", "AUTH_REQUIRED"):
                    report["outcome"] = state
                else:
                    for pass_no in range(2 if mode == "preview" and state == "VISIBLE" else 1):
                        if pass_no:
                            page.mouse.wheel(0, 600)
                            page.wait_for_timeout(900)
                            state = classify_state(page.url, page.title(), page.locator("body").inner_text(timeout=4000)[:10000])
                            if state in ("ACCESS_RESTRICTED", "AUTH_REQUIRED", "LOGIN_PROMPT"):
                                report["outcome"] = state
                                break
                        links = page.locator(SELECTOR)
                        for index in range(min(links.count(), maximum * 3)):
                            try:
                                anchor = links.nth(index)
                                link = canonical_note_url(anchor.get_attribute("href") or "")
                                if not link or link in cards:
                                    continue
                                text = anchor.inner_text(timeout=1500).strip()
                                cards[link] = {"note_id": link.rsplit("/", 1)[-1], "note_url": link,
                                               "title": text.splitlines()[0][:160] if text else "",
                                               "desc": text[:1000], "source": "public_card",
                                               "content_complete": False}
                                if len(cards) == maximum:
                                    break
                            except Exception:
                                continue
                        if len(cards) == maximum:
                            break
                    report.setdefault("outcome", "PUBLIC_PREVIEW_FOUND" if cards else
                                      "LOGIN_PROMPT" if state == "LOGIN_PROMPT" else "NO_PUBLIC_CARDS")
                    # For preview mode, a single normal UI click verifies whether detail is accessible.
                    if mode == "preview" and cards and state == "VISIBLE":
                        first = next(iter(cards))
                        anchors = page.locator(SELECTOR)
                        for index in range(min(anchors.count(), maximum * 3)):
                            anchor = anchors.nth(index)
                            if canonical_note_url(anchor.get_attribute("href") or "") != first:
                                continue
                            try:
                                anchor.click(timeout=5000)
                                page.wait_for_timeout(1400)
                                detail_page = context.pages[-1]
                                detail_body = detail_page.locator("body").inner_text(timeout=3500)[:10000]
                                detail_state = classify_state(detail_page.url, detail_page.title(), detail_body)
                                report["detail_state"] = detail_state
                                report["detail_path"] = urlparse(detail_page.url).path
                                detail_page.screenshot(path=str(output / "detail.png"), full_page=False)
                                if detail_state in ("ACCESS_RESTRICTED", "AUTH_REQUIRED", "LOGIN_PROMPT"):
                                    report["outcome"] = detail_state
                                else:
                                    report["outcome"] = "DETAIL_OPENED_NOT_VERIFIED_COMPLETE"
                            except Exception as exc:
                                report["detail_error_type"] = type(exc).__name__
                            break
            except Exception as exc:
                report["outcome"] = "NAVIGATION_ERROR"
                report["error_type"] = type(exc).__name__
            finally:
                context.close()
        finally:
            browser.close()
    report["visible_card_count"] = len(cards)
    with (output / "visible_cards.jsonl").open("w", encoding="utf-8") as f:
        for card in cards.values():
            f.write(json.dumps(card, ensure_ascii=False) + "\n")
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("probe", "preview"), default="probe")
    parser.add_argument("--max-cards", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/hosted"))
    args = parser.parse_args()
    if args.max_cards < 1 or args.max_cards > 20:
        parser.error("--max-cards should be 1 to 20")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        report = inspect(args.mode, args.output_dir, args.max_cards)
    except Exception as exc:
        report = {"outcome": "BROWSER_LAUNCH_ERROR", "error_type": type(exc).__name__}
        (args.output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
