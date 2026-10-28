import json
import tempfile
import unittest
from pathlib import Path
from scripts.research_core import (
    canonical_note_url, note_topics, parse_profile_url,
    prepare_analysis_input, render_evidence_report, write_outputs,
)


class ResearchCoreTests(unittest.TestCase):
    def test_creator_url_and_no_query_in_report(self):
        url, creator = parse_profile_url(
            "https://www.xiaohongshu.com/user/profile/63572290000000001901d19a?xsec_token=SECRET"
        )
        self.assertEqual(creator, "63572290000000001901d19a")
        self.assertNotIn("SECRET", url)

    def test_reject_untrusted_creator_link(self):
        for bad in (
            "http://www.xiaohongshu.com/user/profile/63572290000000001901d19a",
            "https://evil.example/user/profile/63572290000000001901d19a",
            "https://www.xiaohongshu.com/explore/63572290000000001901d19a",
        ):
            with self.assertRaises(ValueError):
                parse_profile_url(bad)

    def test_note_url(self):
        self.assertEqual(
            canonical_note_url("/explore/697b4785000000000e03e349?xsec_token=PRIVATE"),
            "https://www.xiaohongshu.com/explore/697b4785000000000e03e349",
        )
        self.assertIsNone(canonical_note_url("https://other.example/explore/697b4785000000000e03e349"))

    def test_topics_and_no_fake_claims(self):
        row = {"title": "LangGraph Agent 技术面试", "body": "如何处理 checkpoint？"}
        self.assertIn("面试与面经", note_topics(row))
        self.assertIn("LangGraph 与工作流", note_topics(row))

    def test_outputs_are_local_and_source_grounded(self):
        item = {
            "note_id": "697b4785000000000e03e349",
            "url": "https://www.xiaohongshu.com/explore/697b4785000000000e03e349",
            "navigation_url": "https://www.xiaohongshu.com/explore/697b4785000000000e03e349?xsec_token=SECRET",
            "title": "Agent 面试",
            "body": "讨论 Agent 如何规划",
            "status": "text_read", "images_not_transcribed": True,
        }
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            write_outputs(d, "https://www.xiaohongshu.com/user/profile/63572290000000001901d19a",
                          "Agent 面试", [item], 1, "")
            notes = (d / "notes.jsonl").read_text(encoding="utf-8")
            report = (d / "report.md").read_text(encoding="utf-8")
            self.assertNotIn("SECRET", notes)
            self.assertIn(item["url"], report)
            self.assertIn("图片文字与视频尚未转写", report)
            self.assertTrue((d / "analysis_input.json").exists())
            self.assertEqual(json.loads((d / "manifest.json").read_text(encoding="utf-8"))["text_read"], 1)


if __name__ == "__main__":
    unittest.main()
