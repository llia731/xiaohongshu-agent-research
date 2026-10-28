#!/usr/bin/env python3
"""QR-first login manager for a single, manually triggered GitHub Actions run.

Checks public access first, dismisses ordinary login prompts once, and only opens
login when explicitly required. Never stores cookies/browser state or bypasses
CAPTCHAs, security restrictions, or other access controls.
"""
from __future__ import annotations
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from scripts.auth_manager import classify_page_state, detect_login_methods, is_security_restriction

PROFILE = "https://www.xiaohongshu.com/user/profile/63572290000000001901d19a"
HOME = "https://www.xiaohongshu.com"
NOTE_SELECTOR = 'a[href*="/explore/"], a[href*="/discovery/item/"]'

def publish(directory: Path, state: str, **metadata: object) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    result = {
        "state": state,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "auth_method_preference": "qrcode",
        "session_persisted": False,
        **metadata,
    }
    temp = directory / "status.json.tmp"
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(directory / "status.json")

def page_body(page, limit: int = 12000) -> str:
    try:
        return page.locator("body").inner_text(timeout=3500)[:limit]
    except Exception:
        return ""

def is_logged_in(page, context, baseline_web_session: str | None = None) -> bool:
    """Require explicit UI evidence or a session cookie changed after login."""
    try:
        body = page_body(page, 8000)
        if any(phrase in body for phrase in ("退出登录", "切换账号", "账号与安全")):
            return True
        cookies = context.cookies(HOME)
        current = next((c.get("value") for c in cookies if c.get("name") == "web_session"), None)
        return bool(current and baseline_web_session and current != baseline_web_session)
    except Exception:
        return False

def visible_note_count(page) -> int:
    try:
        return page.locator(NOTE_SELECTOR).count()
    except Exception:
        return 0

def login_modal_visible(page, body: str | None = None) -> bool:
    try:
        dialogs = page.get_by_role("dialog")
        if any(dialog.is_visible() for dialog in dialogs.all()):
            return True
    except Exception:
        pass
    body = body if body is not None else page_body(page)
    if any(phrase in body for phrase in ("登录即可查看", "登录后查看更多", "手机号登录")):
        return True
    for selector in ('[class*="login-modal"]', '[class*="loginDialog"]', '[class*="login-dialog"]'):
        try:
            if any(item.is_visible() for item in page.locator(selector).all()):
                return True
        except Exception:
            continue
    return False

def inspect_page(page, context=None, baseline_web_session: str | None = None) -> dict:
    try:
        title = page.title()[:160]
    except Exception:
        title = ""
    body = page_body(page)
    logged_in = is_logged_in(page, context, baseline_web_session) if context else False
    card_count = visible_note_count(page)
    modal = login_modal_visible(page, body)
    assessment = classify_page_state(
        page.url, title, body, has_note_cards=card_count > 0,
        logged_in=logged_in, login_modal_visible=modal,
    )
    return {
        "state": assessment.state, "action": assessment.action, "reason": assessment.reason,
        "page_path": urlparse(page.url).path, "page_title": title,
        "visible_note_anchor_count": card_count, "login_modal_visible": modal,
        "login_methods": list(detect_login_methods(body)), "logged_in_evidence": logged_in,
    }

def _visible(locator) -> bool:
    try:
        return locator.is_visible()
    except Exception:
        return False

def dismiss_login_prompt(page) -> bool:
    """Click a clearly labelled close control once, not arbitrary modal buttons."""
    selectors = (
        '[role="dialog"] button[aria-label*="关闭"]',
        '[role="dialog"] button[title*="关闭"]',
        '[role="dialog"] button[aria-label*="close" i]',
        'button[aria-label*="关闭"]', 'button[title*="关闭"]',
        'button[aria-label*="close" i]', 'button:has-text("×")', 'button:has-text("✕")',
    )
    for selector in selectors:
        try:
            for item in page.locator(selector).all():
                if _visible(item):
                    item.click(timeout=1800)
                    page.wait_for_timeout(650)
                    return True
        except Exception:
            continue
    # Some overlays use an unlabeled X. Only click a blank button at the dialog's top-right.
    try:
        for dialog in page.get_by_role("dialog").all():
            if not _visible(dialog):
                continue
            box = dialog.bounding_box()
            if not box:
                continue
            for button in dialog.locator("button").all():
                if not _visible(button):
                    continue
                label = " ".join(filter(None, [
                    button.get_attribute("aria-label"), button.get_attribute("title"),
                    button.inner_text(timeout=500),
                ])).strip()
                button_box = button.bounding_box()
                if (not label and button_box
                    and button_box["x"] > box["x"] + box["width"] * 0.70
                    and button_box["y"] < box["y"] + box["height"] * 0.28):
                    button.click(timeout=1800)
                    page.wait_for_timeout(650)
                    return True
    except Exception:
        pass
    return False

def open_login_ui(page) -> bool:
    """Open the site's regular login UI using a visible Login control."""
    if login_modal_visible(page) or urlparse(page.url).path.startswith("/login"):
        return True
    for selector in ('button:has-text("登录")', 'a:has-text("登录")', '[role="button"]:has-text("登录")'):
        try:
            for item in page.locator(selector).all():
                if not _visible(item):
                    continue
                label = item.inner_text(timeout=700).strip()
                if label not in ("登录", "立即登录", "登录/注册", "登录注册"):
                    continue
                item.click(timeout=2500)
                page.wait_for_timeout(900)
                if login_modal_visible(page) or urlparse(page.url).path.startswith("/login"):
                    return True
        except Exception:
            continue
    return urlparse(page.url).path.startswith("/login")

def _qr_candidates(page) -> list[tuple[str, object]]:
    selectors = (
        "img.qrcode-img", ".qrcode img", 'img[alt*="二维码"]', 'img[alt*="扫码"]',
        'img[class*="qrcode"]', 'img[class*="qr-code"]', '[class*="qrcode"] img',
        '[class*="qrCode"] img', '[class*="qr-code"] img', '[class*="qrcode"]',
        '[class*="qrCode"]', '[class*="qr-code"]',
    )
    found, seen = [], set()
    for selector in selectors:
        try:
            for item in page.locator(selector).all():
                if not _visible(item):
                    continue
                box = item.bounding_box()
                if not box or box["width"] < 70 or box["height"] < 70:
                    continue
                key = f'{selector}:{round(box["x"])}:{round(box["y"])}:{round(box["width"])}:{round(box["height"])}'
                if key in seen:
                    continue
                seen.add(key)
                if item.evaluate("(el) => el.tagName.toLowerCase() === 'img'"):
                    try:
                        if not item.evaluate("(el) => el.complete && el.naturalWidth > 0"):
                            continue
                    except Exception:
                        continue
                found.append((selector, item))
        except Exception:
            continue
    body = page_body(page)
    if any(label in body for label in ("扫码登录", "二维码登录", "微信扫码")):
        try:
            for item in page.locator("canvas").all():
                if not _visible(item):
                    continue
                box = item.bounding_box()
                if box and box["width"] >= 90 and box["height"] >= 90:
                    found.append(("canvas (login UI advertises QR)", item))
        except Exception:
            pass
    return found

def qr_locator(page):
    candidates = _qr_candidates(page)
    return candidates[0][1] if candidates else None

def _click_login_method_control(page) -> str | None:
    selectors = (
        'button[aria-label*="二维码"]', 'button[title*="二维码"]',
        '[role="button"][aria-label*="二维码"]', 'button[aria-label*="扫码"]',
        'button[title*="扫码"]', 'button:has-text("二维码登录")',
        'button:has-text("扫码登录")', 'text="二维码登录"', 'text="扫码登录"',
        'text="其他登录方式"', 'text="其他方式登录"', 'text="更多登录方式"', 'text="更多方式"',
    )
    for selector in selectors:
        try:
            for item in page.locator(selector).all():
                if not _visible(item):
                    continue
                try:
                    item.click(timeout=2200)
                    page.wait_for_timeout(850)
                    return selector
                except Exception:
                    continue
        except Exception:
            continue
    return None

def login_ui_diagnostics(page) -> dict:
    """Collect non-secret UI metadata; never include cookie values or image URLs."""
    body = page_body(page, 12000)
    buttons = []
    try:
        for item in page.locator("button, [role='button'], a").all():
            if not _visible(item):
                continue
            label = " ".join(filter(None, [
                item.get_attribute("aria-label"), item.get_attribute("title"),
                item.inner_text(timeout=300),
            ])).strip()
            if label and any(token in label for token in
                ("登录", "扫码", "二维码", "手机", "验证码", "密码", "其他", "更多", "刷新")):
                if label not in buttons:
                    buttons.append(label[:60])
            if len(buttons) >= 20:
                break
    except Exception:
        pass
    images = []
    try:
        for item in page.locator("img, canvas, [class*='qrcode'], [class*='qr-code']").all():
            if not _visible(item):
                continue
            box = item.bounding_box()
            if not box:
                continue
            images.append({
                "tag": item.evaluate("(el) => el.tagName.toLowerCase()"),
                "alt": (item.get_attribute("alt") or "")[:60],
                "class": (item.get_attribute("class") or "")[:100],
                "width": round(box["width"]), "height": round(box["height"]),
            })
            if len(images) >= 20:
                break
    except Exception:
        pass
    return {
        "page_path": urlparse(page.url).path, "page_title": page.title()[:160],
        "visible_login_methods": list(detect_login_methods(body)),
        "visible_login_controls": buttons, "visible_image_candidates": images,
        "body_signals": {
            "has_phone_input": any(x in body for x in ("输入手机号", "手机号", "手机号码")),
            "has_verification_code": any(x in body for x in ("验证码", "获取验证码")),
            "has_password_login": any(x in body for x in ("密码登录", "账号密码")),
            "has_qr_login_text": any(x in body for x in ("扫码登录", "二维码登录", "微信扫码")),
            "has_security_restriction": is_security_restriction(page.url, page.title(), body),
        },
    }

def extract_visible_cards(page, directory: Path, source: str, baseline_session: str | None = None) -> int:
    from scripts.hosted_browser_research import canonical_note_url
    body = page_body(page)
    assessment = classify_page_state(
        page.url, page.title(), body, has_note_cards=visible_note_count(page) > 0,
        logged_in=is_logged_in(page, page.context, baseline_session),
        login_modal_visible=login_modal_visible(page, body),
    )
    if assessment.state in {"ACCESS_RESTRICTED", "AUTH_REQUIRED", "LOGIN_PROMPT"}:
        return -1
    collected = {}
    links = page.locator(NOTE_SELECTOR)
    for index in range(min(links.count(), 40)):
        try:
            anchor = links.nth(index)
            url = canonical_note_url(anchor.get_attribute("href") or "")
            if not url or url in collected:
                continue
            text = anchor.inner_text(timeout=1200).strip()
            collected[url] = {
                "note_id": url.rsplit("/", 1)[-1], "note_url": url,
                "title": text.splitlines()[0][:160] if text else "",
                "desc": text[:1000], "source": source, "content_complete": False,
            }
            if len(collected) >= 10:
                break
        except Exception:
            continue
    with (directory / "visible_cards.jsonl").open("w", encoding="utf-8") as file:
        for card in collected.values():
            file.write(json.dumps(card, ensure_ascii=False) + "\n")
    return len(collected)

def _session_cookie(context) -> str | None:
    try:
        return next((c.get("value") for c in context.cookies(HOME) if c.get("name") == "web_session"), None)
    except Exception:
        return None

def run(output: Path, timeout_seconds: int) -> None:
    from playwright.sync_api import sync_playwright
    output.mkdir(parents=True, exist_ok=True)
    publish(output, "STARTING", decision="先检查目标主页的匿名可访问性")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN")
            page = context.new_page()
            try:
                page.goto(PROFILE, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(1800)
            except Exception as exc:
                publish(output, "BROWSER_ERROR", error_type=type(exc).__name__, stage="open_profile")
                return

            initial = inspect_page(page, context)
            if initial["state"] == "ACCESS_RESTRICTED":
                publish(output, "ACCESS_RESTRICTED", reason=initial["reason"], diagnostics=initial)
                return
            if initial["state"] == "AUTHENTICATED":
                count = extract_visible_cards(page, output, "authenticated_visible_card")
                publish(output, "AUTHENTICATED", visible_card_count=max(count, 0),
                        reason="页面已有明确登录证据；没有重复登录。")
                return
            if initial["state"] == "PUBLIC_ACCESS":
                count = extract_visible_cards(page, output, "public_visible_card")
                publish(output, "PUBLIC_ACCESS", visible_card_count=max(count, 0),
                        reason="目标主页可匿名查看；未启动登录流程。", diagnostics=initial)
                return

            saw_login_prompt = initial["state"] == "LOGIN_PROMPT"
            if saw_login_prompt:
                dismissed = dismiss_login_prompt(page)
                page.wait_for_timeout(800)
                after_close = inspect_page(page, context)
                if after_close["state"] == "ACCESS_RESTRICTED":
                    publish(output, "ACCESS_RESTRICTED", reason=after_close["reason"], diagnostics=after_close)
                    return
                if after_close["state"] in {"PUBLIC_ACCESS", "AUTHENTICATED"}:
                    count = extract_visible_cards(
                        page, output,
                        "authenticated_visible_card" if after_close["state"] == "AUTHENTICATED" else "public_visible_card",
                    )
                    publish(output, after_close["state"], visible_card_count=max(count, 0),
                            reason="关闭普通登录提示后，内容仍可访问；无需扫码。",
                            login_prompt_dismissed=dismissed, diagnostics=after_close)
                    return
                initial = after_close
                if initial["state"] == "UNKNOWN":
                    # The prompt explicitly said notes require login, but closing it
                    # removed the text; with no cards exposed, treat this as auth-required.
                    initial = {**initial, "state": "AUTH_REQUIRED", "reason": "关闭登录提示后没有可见帖子，原页面明确提示需要登录。"}

            if initial["state"] == "UNKNOWN":
                page.wait_for_timeout(1800)
                initial = inspect_page(page, context)
                if initial["state"] == "PUBLIC_ACCESS":
                    count = extract_visible_cards(page, output, "public_visible_card")
                    publish(output, "PUBLIC_ACCESS", visible_card_count=max(count, 0),
                            reason="等待页面稳定后确认可匿名访问。", diagnostics=initial)
                    return
                if initial["state"] not in {"AUTH_REQUIRED", "LOGIN_PROMPT"}:
                    publish(output, "PAGE_STATE_UNCLEAR",
                            reason="页面没有明确要求登录，也没有可验证的公开帖子卡片；不自动触发登录。",
                            diagnostics=login_ui_diagnostics(page))
                    return

            try:
                page.goto(HOME, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(900)
            except Exception as exc:
                publish(output, "BROWSER_ERROR", error_type=type(exc).__name__, stage="open_login_home")
                return
            if is_security_restriction(page.url, page.title(), page_body(page)):
                publish(output, "ACCESS_RESTRICTED", reason="打开登录页面时触发平台安全限制。",
                        diagnostics=login_ui_diagnostics(page))
                return

            baseline_session = _session_cookie(context)
            opened = open_login_ui(page)
            if is_security_restriction(page.url, page.title(), page_body(page)):
                publish(output, "ACCESS_RESTRICTED", reason="登录界面出现平台安全限制。",
                        diagnostics=login_ui_diagnostics(page))
                return
            qr = qr_locator(page)
            click_attempts = []
            for _ in range(4):
                if qr is not None:
                    break
                action = _click_login_method_control(page)
                if not action:
                    break
                click_attempts.append(action)
                if is_security_restriction(page.url, page.title(), page_body(page)):
                    publish(output, "ACCESS_RESTRICTED", reason="切换登录方式时出现平台安全限制。",
                            diagnostics=login_ui_diagnostics(page), login_control_attempts=click_attempts)
                    return
                qr = qr_locator(page)

            if qr is None:
                publish(
                    output, "LOGIN_UI_NO_QR",
                    reason="已检查登录页面并尝试官方二维码入口，但没有检测到可见、已加载的二维码。",
                    login_ui_opened=opened, login_control_attempts=click_attempts,
                    diagnostics=login_ui_diagnostics(page),
                )
                return

            # Only the QR element is uploaded; never capture/upload a full-page login screenshot.
            qr.screenshot(path=str(output / "scan_me.png"), timeout=5000)
            publish(output, "QR_READY",
                    reason="二维码已加载。请在私有仓库 Actions 运行页下载并尽快扫码。",
                    login_ui_opened=opened, login_control_attempts=click_attempts,
                    diagnostics=login_ui_diagnostics(page))

            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                body = page_body(page)
                if is_security_restriction(page.url, page.title(), body):
                    publish(output, "ACCESS_RESTRICTED", reason="等待扫码期间出现平台安全限制。")
                    return
                if any(text in body for text in ("二维码已过期", "二维码过期", "请刷新二维码")):
                    publish(output, "LOGIN_EXPIRED", reason="页面提示二维码已过期；请重新手动运行工作流。")
                    return
                if is_logged_in(page, context, baseline_session):
                    try:
                        page.goto(PROFILE, wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_timeout(1400)
                        profile_state = inspect_page(page, context, baseline_session)
                        if profile_state["state"] == "ACCESS_RESTRICTED":
                            publish(output, "AUTHENTICATED_PROFILE_UNAVAILABLE",
                                    reason="登录状态已确认，但目标主页受到平台访问限制。",
                                    diagnostics=profile_state)
                            return
                        count = extract_visible_cards(page, output, "authenticated_visible_card", baseline_session)
                        if count < 0:
                            publish(output, "AUTHENTICATED_PROFILE_UNAVAILABLE",
                                    reason="登录状态已确认，但目标主页仍要求登录或无法读取帖子。",
                                    diagnostics=inspect_page(page, context, baseline_session))
                        else:
                            publish(output, "AUTHENTICATED", visible_card_count=count,
                                    reason="登录状态已确认；只保存可见帖子卡片，不代表已采集完整帖子。")
                        return
                    except Exception as exc:
                        publish(output, "AUTHENTICATED_PROFILE_UNAVAILABLE", error_type=type(exc).__name__)
                        return
                time.sleep(1)
            body = page_body(page)
            if any(text in body for text in ("二维码已过期", "二维码过期", "请刷新二维码")):
                publish(output, "LOGIN_EXPIRED", reason="二维码已过期。")
            else:
                publish(output, "LOGIN_TIMEOUT", reason="等待扫码超时；本次运行结束，不会自动无限重试。")
        finally:
            browser.close()

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/qr"))
    parser.add_argument("--timeout-seconds", type=int, default=150)
    args = parser.parse_args()
    if not 30 <= args.timeout_seconds <= 180:
        parser.error("timeout must be between 30 and 180 seconds")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        run(args.output_dir, args.timeout_seconds)
    except Exception as exc:
        publish(args.output_dir, "BROWSER_ERROR", error_type=type(exc).__name__)

if __name__ == "__main__":
    main()
