import unittest
from scripts.test_server_access import DEFAULT_URL
from scripts.auth_manager import classify_page_state
from scripts.research_core import parse_profile_url

class ServerProbeTests(unittest.TestCase):
    def test_target(self):
        _, creator = parse_profile_url(DEFAULT_URL)
        self.assertEqual(creator, "63572290000000001901d19a")
    def test_ip_risk_without_redirect(self):
        state = classify_page_state(DEFAULT_URL, "程序员峰哥 - 小红书",
                                    "安全限制 IP存在风险，请切换可靠网络环境后重试 300012")
        self.assertEqual(state.state, "ACCESS_RESTRICTED")
