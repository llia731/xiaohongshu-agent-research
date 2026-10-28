import unittest
from scripts.hosted_browser_research import classify_state, canonical_note_url

class HostedResearchTests(unittest.TestCase):
    def test_security_state(self):
        self.assertEqual(classify_state("https://www.xiaohongshu.com/website-login/error", "小红书", ""), "ACCESS_RESTRICTED")
        self.assertEqual(classify_state("https://www.xiaohongshu.com/user/profile/x", "安全限制", ""), "ACCESS_RESTRICTED")

    def test_login_state(self):
        self.assertEqual(classify_state("https://www.xiaohongshu.com/login", "小红书", ""), "AUTH_REQUIRED")
        self.assertEqual(classify_state("https://www.xiaohongshu.com/user/profile/x", "", "登录即可查看 Ta 的笔记"), "LOGIN_PROMPT")

    def test_url_allowlist(self):
        self.assertEqual(canonical_note_url("/explore/654321abcdef123456789abc?xsec_token=secret"), "https://www.xiaohongshu.com/explore/654321abcdef123456789abc")
        self.assertIsNone(canonical_note_url("https://example.org/explore/654321abcdef123456789abc"))
