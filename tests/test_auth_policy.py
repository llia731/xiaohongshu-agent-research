import json
import tempfile
import unittest
from pathlib import Path
from scripts.auth_policy import decide_auth_action
from scripts.github_qr_worker import publish

class AuthenticationPolicyTests(unittest.TestCase):
    def test_anonymous_priority(self):
        self.assertEqual(decide_auth_action("PUBLIC_ACCESS").action, "CONTINUE_ANONYMOUS")
        self.assertEqual(decide_auth_action("LOGIN_PROMPT").action, "DISMISS_PROMPT_ONCE")
    def test_qr_first_when_required(self):
        self.assertEqual(decide_auth_action("AUTH_REQUIRED").action, "REQUEST_QR_LOGIN")
        self.assertEqual(decide_auth_action("SESSION_EXPIRED").action, "REQUEST_QR_LOGIN")
    def test_stop_security(self):
        self.assertEqual(decide_auth_action("ACCESS_RESTRICTED").action, "STOP")
        self.assertEqual(decide_auth_action("UNKNOWN").action, "STOP_AND_INSPECT")
    def test_state_metadata_contains_no_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            publish(Path(tmp), "QR_READY", reason="scan")
            saved = json.loads((Path(tmp) / "status.json").read_text())
            self.assertEqual(saved["state"], "QR_READY")
            self.assertFalse(saved["session_persisted"])
            self.assertNotIn("cookie", saved)
