import json
import tempfile
import unittest
from pathlib import Path

from scripts.filter_agent_posts import classify, process
from scripts.configure_mediacrawler import parse_profile_url


class FilterTests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(classify({"title": "AI Agent 面试题汇总"})[0], "direct")
        self.assertEqual(classify({"title": "后端面试总结"})[0], "review")
        self.assertEqual(classify({"title": "Agent Memory 原理"})[0], "related")
        self.assertEqual(classify({"title": "周末运动"})[0], "other")

    def test_dedupe_export_and_image_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "creator_contents_test.jsonl"
            rows = [
                {"note_id": "a", "title": "Agent 面试总结", "desc": "一", "image_list": "https://example.com/a.png"},
                {"note_id": "b", "title": "日常笔记"},
                {"note_id": "a", "title": "Agent 面试总结", "desc": "更新", "image_list": "https://example.com/a.png"},
            ]
            source.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows), encoding="utf-8")
            out = Path(tmp) / "out"
            result = process([source], out)
            self.assertEqual(result["unique_posts"], 2)
            self.assertEqual(result["direct_matches"], 1)
            self.assertEqual(result["image_review_queue"], 1)
            self.assertTrue((out / "analysis_input.jsonl").exists())

    def test_profile_url_validation(self):
        good = "https://www.xiaohongshu.com/user/profile/63572290000000001901d19a?xsec_token=example&xsec_source=pc_user"
        self.assertEqual(parse_profile_url(good), good)
        with self.assertRaises(ValueError):
            parse_profile_url("https://www.xiaohongshu.com/user/profile/wrong")


if __name__ == "__main__":
    unittest.main()
