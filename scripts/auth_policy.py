"""High-level decisions for browser-based Xiaohongshu research."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthDecision:
    action: str
    reason: str


def decide_auth_action(page_state: str, login_method: str = "qrcode") -> AuthDecision:
    """Return a safe next action from an observed page state."""
    if login_method != "qrcode":
        raise ValueError("Only QR-code login is supported in this project.")

    if page_state in ("VISIBLE", "PUBLIC_ACCESS", "PUBLIC_PREVIEW_FOUND"):
        return AuthDecision("CONTINUE_ANONYMOUS", "公开内容可访问，无需登录。")
    if page_state == "AUTHENTICATED":
        return AuthDecision("CONTINUE_AUTHENTICATED", "已经确认登录状态，无需重复登录。")
    if page_state in ("LOGIN_PROMPT", "LOGIN_MODAL_DISMISSIBLE"):
        return AuthDecision("DISMISS_PROMPT_ONCE", "先关闭普通登录提示，再检查公开内容是否可读。")
    if page_state in ("AUTH_REQUIRED", "SESSION_EXPIRED"):
        return AuthDecision("REQUEST_QR_LOGIN", "确实需要登录时，优先使用官方二维码登录。")
    if page_state == "QR_READY":
        return AuthDecision("WAIT_FOR_USER_SCAN", "二维码已就绪，等待用户在手机端确认。")
    if page_state in ("LOGIN_UI_NO_QR", "QR_UNAVAILABLE"):
        return AuthDecision("CAPTURE_LOGIN_DIAGNOSTICS", "未找到二维码，记录登录方式和页面元素后停止。")
    if page_state in ("LOGIN_EXPIRED", "LOGIN_TIMEOUT"):
        return AuthDecision("REQUEST_NEW_MANUAL_RUN", "二维码已过期或等待超时，请用户手动重新启动。")
    if page_state in ("ACCESS_RESTRICTED", "ACCESS_RESTRICTED_BY_PLATFORM"):
        return AuthDecision("STOP", "平台访问受限，停止自动操作，不尝试绕过。")
    if page_state == "AUTHENTICATED_PROFILE_UNAVAILABLE":
        return AuthDecision("STOP_AND_REPORT", "登录已确认，但目标主页仍不可访问。")
    return AuthDecision("STOP_AND_INSPECT", "页面状态不明确，保存诊断信息后停止。")
