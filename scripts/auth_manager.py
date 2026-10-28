"""Page-state and login-method detection for Xiaohongshu browser workflows."""
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse

SECURITY_PATHS = ("/website-login/error", "/website-login/security")
LOGIN_PATHS = ("/login", "/website-login/login")
SECURITY_PHRASES = ("安全限制", "请通过安全验证", "访问受到限制", "账号存在风险")
LOGIN_REQUIRED_PHRASES = ("请先登录", "登录后查看", "登录后继续", "登录后可查看")
LOGIN_PROMPT_PHRASES = ("登录即可查看", "登录后查看更多", "登录探索更多内容")
QR_PHRASES = ("扫码登录", "二维码登录", "微信扫码")
PHONE_PHRASES = ("手机号登录", "手机号码登录", "短信验证码", "验证码登录")
PASSWORD_PHRASES = ("密码登录", "账号密码")
OTHER_METHOD_PHRASES = ("其他登录方式", "其他方式登录", "更多登录方式", "更多方式")

@dataclass(frozen=True)
class PageAssessment:
    state: str
    action: str
    reason: str
    login_methods: tuple[str, ...] = ()

def is_security_restriction(url: str, title: str = "", body: str = "") -> bool:
    path = urlparse(url).path
    return (
        any(path.startswith(prefix) for prefix in SECURITY_PATHS)
        or any(phrase in title for phrase in SECURITY_PHRASES)
        or any(phrase in body for phrase in SECURITY_PHRASES)
    )

def detect_login_methods(body: str) -> tuple[str, ...]:
    groups = (
        ("QR_CODE", QR_PHRASES),
        ("PHONE_OTP", PHONE_PHRASES),
        ("PASSWORD", PASSWORD_PHRASES),
        ("OTHER_METHODS", OTHER_METHOD_PHRASES),
    )
    return tuple(name for name, phrases in groups if any(phrase in body for phrase in phrases))

def classify_page_state(
    url: str, title: str = "", body: str = "", *,
    has_note_cards: bool = False, logged_in: bool = False,
    login_modal_visible: bool = False,
) -> PageAssessment:
    """Explicit security restrictions win; ordinary login prompts are dismissible."""
    path = urlparse(url).path
    methods = detect_login_methods(body)
    if is_security_restriction(url, title, body):
        return PageAssessment("ACCESS_RESTRICTED", "STOP",
                              "检测到平台安全限制；停止自动操作，不尝试绕过。", methods)
    if any(path == prefix or path.startswith(prefix + "/") for prefix in LOGIN_PATHS):
        return PageAssessment("AUTH_REQUIRED", "OPEN_QR_LOGIN",
                              "当前页面进入登录流程；优先查找二维码登录方式。", methods)
    if logged_in:
        return PageAssessment("AUTHENTICATED", "CONTINUE_AUTHENTICATED",
                              "页面存在已登录的明确证据，无需重复登录。", methods)
    if login_modal_visible or any(phrase in body for phrase in LOGIN_PROMPT_PHRASES):
        return PageAssessment("LOGIN_PROMPT", "DISMISS_PROMPT_ONCE",
                              "发现普通登录提示；先尝试关闭一次，再检查公开内容是否可读。", methods)
    if any(phrase in body for phrase in LOGIN_REQUIRED_PHRASES):
        return PageAssessment("AUTH_REQUIRED", "OPEN_QR_LOGIN",
                              "页面明确提示需要登录；优先查找二维码登录方式。", methods)
    if has_note_cards:
        return PageAssessment("PUBLIC_ACCESS", "CONTINUE_ANONYMOUS",
                              "页面包含可见帖子卡片且未发现登录门槛；继续匿名浏览。", methods)
    return PageAssessment("UNKNOWN", "WAIT_AND_RECHECK",
                          "尚无足够证据判断登录状态；等待页面稳定后再检查，不立即登录。", methods)

def should_fail_workflow(state: str) -> bool:
    return state not in {"PUBLIC_ACCESS", "AUTHENTICATED"}
