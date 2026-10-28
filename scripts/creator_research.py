"""Read a creator through a visible, local Chrome window; never bypass access gates."""
from __future__ import annotations

import argparse
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
from time import monotonic
from urllib.parse import urljoin

from scripts.auth_manager import is_security_restriction
from scripts.research_core import (
    canonical_note_url, parse_profile_url, prepare_analysis_input, write_outputs,
)

LINKS = 'a[href*="/explore/"], a[href*="/discovery/item/"]'
TITLE_SELECTORS = ("#detail-title", ".note-detail-title", ".note-title", "h1")
BODY_SELECTORS = ("#detail-desc", "#detail-content", ".note-text", ".note-content", ".desc", ".note-desc")
LOGIN_TERMS = ("登录即可查看", "请先登录", "登录后查看", "登录后查看更多")


def page_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=3000)[:12000]
    except Exception:
        return ""


def limited_text(page, selectors: tuple[str, ...], limit: int = 6000) -> str:
    for selector in selectors:
        try:
            for item in page.locator(selector).all()[:8]:
                if item.is_visible():
                    value = item.inner_text(timeout=1200).strip()
                    if value:
                        return value[:limit]
        except Exception:
            continue
    return ""


def note_cards(page, collected: dict[str, dict], max_notes: int) -> None:
    links = page.locator(LINKS)
    for index in range(min(links.count(), 180)):
        try:
            a = links.nth(index)
            href = a.get_attribute("href") or ""
            url = canonical_note_url(urljoin("https://www.xiaohongshu.com", href))
            if not url or url in collected:
                continue
            preview = a.inner_text(timeout=1000).strip()
            collected[url] = {
                "note_id": url.rstrip("/").split("/")[-1],
                "url": url, "navigation_url": urljoin("https://www.xiaohongshu.com", href),
                "title": preview.splitlines()[0][:180] if preview else "",
                "preview": preview[:1200],
                "status": "not_read", "images_not_transcribed": True,
            }
            if len(collected) >= max_notes:
                return
        except Exception:
            continue


def dismiss_login_once(page) -> bool:
    from scripts.github_qr_worker import dismiss_login_prompt
    return dismiss_login_prompt(page)


def wait_for_visible_cards(page, seconds: int = 120) -> bool:
    """The user may log in normally in this visible Chrome window."""
    print("网页暂时没有可见帖子。若浏览器要求登录，请在弹出的 Chrome 中扫码完成授权。", flush=True)
    end = monotonic() + seconds
    while monotonic() < end:
        current = page_text(page)
        if is_security_restriction(page.url, page.title(), current):
            return False
        if page.locator(LINKS).count():
            # A login overlay can sit over otherwise visible cards.
            if any(term in current for term in LOGIN_TERMS):
                dismiss_login_once(page)
                page.wait_for_timeout(500)
            return bool(page.locator(LINKS).count())
        page.wait_for_timeout(1500)
    return False


def discover_cards(page, maximum: int) -> dict[str, dict]:
    notes: dict[str, dict] = {}
    for _ in range(12):
        if is_security_restriction(page.url, page.title(), page_text(page)):
            break
        note_cards(page, notes, maximum)
        if len(notes) >= maximum:
            break
        before = page.evaluate("document.body.scrollHeight")
        page.mouse.wheel(0, 1000)
        page.wait_for_timeout(1200)
        after = page.evaluate("document.body.scrollHeight")
        if after <= before and len(notes) > 0:
            # still allow another lazy-load attempt
            page.wait_for_timeout(700)
    return notes


def read_note(context, item: dict) -> None:
    detail = context.new_page()
    try:
        detail.goto(item["navigation_url"], wait_until="domcontentloaded", timeout=25000)
        detail.wait_for_timeout(1800)
        page_body = page_text(detail)
        if is_security_restriction(detail.url, detail.title(), page_body):
            item["status"] = "access_restricted"
            return
        if any(term in page_body for term in LOGIN_TERMS) or "/login" in detail.url:
            item["status"] = "login_required"
            return
        title = limited_text(detail, TITLE_SELECTORS, 250)
        body = limited_text(detail, BODY_SELECTORS)
        if title:
            item["title"] = title
        if body:
            item["body"] = body
            item["status"] = "text_read"
        else:
            item["status"] = "preview_only"
    except Exception as exc:
        item["status"] = "read_error"
        item["error_type"] = type(exc).__name__
    finally:
        detail.close()


def optional_ai_report(notes: list[dict], focus: str) -> str | None:
    token = os.getenv("OPENAI_API_KEY", "").strip()
    if not token:
        return None
    import json
    from openai import OpenAI
    client = OpenAI(api_key=token, timeout=90)
    text = prepare_analysis_input(notes, focus)
    if len(text) > 75000:
        text = text[:75000]
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        instructions=(
            "你是知识研究分析员。只基于输入的已读取文字分析；"
            "严格区分博主原文、概括和推断；缺少图片、正文或受限内容时写明局限；"
            "不要推断未阅读帖子的观点。用中文简明表达。"
            "每条核心观点必须附对应笔记原始链接。"
            "组织为：知识体系、核心观点及证据、常见面试题、跨帖联系与差异、缺失内容。"
        ),
        input=text,
        max_output_tokens=3500,
    )
    return response.output_text


def run(raw_url: str, focus: str, max_notes: int, out_root: Path, use_ai: bool) -> Path:
    from playwright.sync_api import sync_playwright
    profile, creator_id = parse_profile_url(raw_url)
    directory = out_root / f"{creator_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    directory.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    discovered = 0
    reason = ""
    with sync_playwright() as p:
        # Dedicated local profile; do not point this at your regular Chrome user profile.
        profile_dir = Path(".local/browser_profile").resolve()
        profile_dir.mkdir(parents=True, exist_ok=True)
        # Windows usually has Google Chrome installed; on Linux, use installed
        # Chrome when present, otherwise the Playwright-managed Chromium.
        channel_opts = (
            {"channel": "chrome"}
            if sys.platform == "win32" or shutil.which("google-chrome") or shutil.which("google-chrome-stable")
            else {}
        )
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False, locale="zh-CN", viewport={"width": 1440, "height": 900},
            **channel_opts,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            print("正在通过本地 Chrome 打开博主主页……", flush=True)
            page.goto(raw_url.strip(), wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2300)
            if is_security_restriction(page.url, page.title(), page_text(page)):
                reason = "平台安全限制，已停止"
            else:
                if any(term in page_text(page) for term in LOGIN_TERMS):
                    dismiss_login_once(page)
                    page.wait_for_timeout(650)
                if page.locator(LINKS).count() == 0:
                    if not wait_for_visible_cards(page):
                        reason = "未能看到可访问的帖子；可能需要登录、页面结构已变或访问受限"
                if not reason:
                    found = discover_cards(page, max_notes)
                    discovered = len(found)
                    print(f"本次发现 {discovered} 条帖子链接。", flush=True)
                    for n, item in enumerate(found.values(), start=1):
                        if is_security_restriction(page.url, page.title(), page_text(page)):
                            reason = "浏览过程中触发安全限制"
                            break
                        print(f"阅读帖子 {n}/{discovered}", flush=True)
                        read_note(context, item)
                        items.append(item)
                        if item["status"] == "access_restricted":
                            reason = "打开帖子后出现安全限制，已停止"
                            break
                        page.wait_for_timeout(1000)
                    if not found:
                        reason = "页面未找到可识别的帖子链接，可能需要适配新版页面"
        finally:
            context.close()
    ai_report = None
    if use_ai and items:
        try:
            ai_report = optional_ai_report(items, focus)
        except Exception as exc:
            reason += f"；AI 分析调用失败：{type(exc).__name__}"
    write_outputs(directory, profile, focus, items, discovered, reason, ai_report)
    print(f"已保存报告和来源记录到：{directory.resolve()}", flush=True)
    return directory


def main():
    parser = argparse.ArgumentParser(description="Local visible-browser creator research")
    parser.add_argument("--profile-url", required=True)
    parser.add_argument("--focus", default="")
    parser.add_argument("--max-notes", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/creator_research"))
    parser.add_argument("--use-ai", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_notes <= 50:
        parser.error("--max-notes must be 1..50")
    try:
        run(args.profile_url, args.focus, args.max_notes, args.output_dir, args.use_ai)
    except Exception as exc:
        print(f"执行失败：{type(exc).__name__}：{str(exc)[:350]}", file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
