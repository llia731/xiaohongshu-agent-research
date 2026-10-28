import unittest
from scripts.auth_manager import classify_page_state, detect_login_methods, should_fail_workflow

class AuthManagerTests(unittest.TestCase):
    def test_security_restriction_has_highest_priority(self):
        result = classify_page_state("https://www.xiaohongshu.com/website-login/error",
                                    "安全限制", "登录", has_note_cards=True)
        self.assertEqual(result.state, "ACCESS_RESTRICTED")
        self.assertEqual(result.action, "STOP")

    def test_already_logged_in_skips_login(self):
        result = classify_page_state("https://www.xiaohongshu.com/user/profile/123",
                                    "小红书", "我的笔记", logged_in=True)
        self.assertEqual(result.state, "AUTHENTICATED")
        self.assertEqual(result.action, "CONTINUE_AUTHENTICATED")

    def test_public_cards_do_not_trigger_login(self):
        result = classify_page_state("https://www.xiaohongshu.com/user/profile/123",
                                    "小红书", "公开内容", has_note_cards=True)
        self.assertEqual(result.state, "PUBLIC_ACCESS")
        self.assertEqual(result.action, "CONTINUE_ANONYMOUS")

    def test_dismiss_prompt_before_login(self):
        result = classify_page_state("https://www.xiaohongshu.com/user/profile/123",
                                    "小红书", "登录即可查看 Ta 的笔记",
                                    has_note_cards=True, login_modal_visible=True)
        self.assertEqual(result.state, "LOGIN_PROMPT")
        self.assertEqual(result.action, "DISMISS_PROMPT_ONCE")

    def test_login_route_requires_auth(self):
        result = classify_page_state("https://www.xiaohongshu.com/login", "登录", "")
        self.assertEqual(result.state, "AUTH_REQUIRED")
        self.assertEqual(result.action, "OPEN_QR_LOGIN")

    def test_detect_available_login_modes(self):
        modes = detect_login_methods("手机号登录 验证码登录 其他登录方式")
        self.assertIn("PHONE_OTP", modes)
        self.assertIn("OTHER_METHODS", modes)
        self.assertNotIn("QR_CODE", modes)

    def test_workflow_success_states_are_explicit(self):
        self.assertFalse(should_fail_workflow("PUBLIC_ACCESS"))
        self.assertFalse(should_fail_workflow("AUTHENTICATED"))
        self.assertTrue(should_fail_workflow("LOGIN_UI_NO_QR"))
        self.assertTrue(should_fail_workflow("ACCESS_RESTRICTED"))

if __name__ == "__main__":
    unittest.main()
