"""Explicit authorization decisions for browser-based XHS research."""
from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class AuthDecision:
    action: str
    reason: str

def decide_auth_action(page_state: str, login_method: str = "qrcode") -> AuthDecision:
    if login_method != "qrcode":
        raise ValueError("Only QR-code login is supported in this project.")
    if page_state in ("VISIBLE", "PUBLIC_ACCESS", "PUBLIC_PREVIEW_FOUND"):
        return AuthDecision("CONTINUE_ANONYMOUS", "公开内容可访问，无需登录")
    if page_state in ("LOGIN_PROMPT", "LOGIN_MODAL_DISMISSIBLE"):
        return AuthDecision("DISMISS_PROMPT_ONCE", "优先关闭普通登录提示，检查是否可继续公开阅读")
    if page_state in ("AUTH_REQUIRED", "SESSION_EXPIRED"):
        return AuthDecision("REQUEST_QR_LOGIN", "确实需要登录，优先使用二维码并等待用户授权")
    if page_state in ("ACCESS_RESTRICTED", "ACCESS_RESTRICTED_BY_PLATFORM"):
        return AuthDecision("STOP", "平台访问限制，不尝试通过登录或重复请求规避")
    return AuthDecision("STOP_AND_INSPECT", "未知页面状态，需要进一步检查")
