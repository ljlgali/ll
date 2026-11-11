"""LAgent 核心层自测（标准库 unittest，不联网、不调模型）。

运行：在 LAgent 目录下执行
    python -m unittest discover -s tests -v
覆盖：Skill frontmatter 解析、Skill 命名校验、Skill 附件路径穿越拒绝、
      文件工具路径边界、危险操作保护、时间工具返回值。
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core import skills as S

try:
    from core import functions as F
    _FUNC_IMPORT_ERROR = None
except Exception as exc:                      # 缺 requests/trafilatura 时只跳过文件工具用例
    F = None
    _FUNC_IMPORT_ERROR = exc


class TestSkillFrontmatter(unittest.TestCase):
    def test_single_line(self):
        text = "---\nname: demo\ndescription: 一句话描述\n---\n# 正文"
        info = S._parse_frontmatter(text)
        self.assertEqual(info["name"], "demo")
        self.assertEqual(info["description"], "一句话描述")

    def test_block_description(self):
        text = "---\nname: demo\ndescription: |\n  第一行\n  第二行\n---\n正文"
        info = S._parse_frontmatter(text)
        self.assertIn("第一行", info["description"])
        self.assertIn("第二行", info["description"])

    def test_no_frontmatter(self):
        self.assertEqual(S._parse_frontmatter("# 没有 frontmatter"), {})


class TestSkillNameValidation(unittest.TestCase):
    def test_reject_bad_names(self):
        for bad in ("大写", "../evil", "a", "-abc", "abc!", "x" * 50):
            res = S.create_skill(bad, "desc", "body")
            self.assertTrue(res.startswith("错误"), f"{bad} 应被拒绝，实际：{res}")

    def test_reject_empty_body(self):
        res = S.create_skill("ok-name", "", "body")
        self.assertTrue(res.startswith("错误"))


class TestSkillLoadGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.skill_dir = root / "skills" / "demo"
        self.skill_dir.mkdir(parents=True)
        (self.skill_dir / "SKILL.md").write_text(
            "---\nname: demo\ndescription: 测试技能\n---\n正文内容", encoding="utf-8"
        )
        (root / "outside.txt").write_text("越权内容", encoding="utf-8")
        self.skills = [{"name": "demo", "description": "测试技能", "path": str(self.skill_dir)}]

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_default_md(self):
        res = S.load_skill(self.skills, "demo")
        self.assertIn("正文内容", res)

    def test_reject_path_traversal(self):
        res = S.load_skill(self.skills, "demo", filename="../outside.txt")
        self.assertIn("拒绝", res)
        self.assertNotIn("越权内容", res)

    def test_unknown_skill(self):
        self.assertTrue(S.load_skill(self.skills, "nope").startswith("错误"))

    def test_long_content_truncated(self):
        big = "字" * (S._MAX_LOAD_CHARS + 500)
        (self.skill_dir / "big.md").write_text(big, encoding="utf-8")
        res = S.load_skill(self.skills, "demo", filename="big.md")
        self.assertIn("已截断", res)
        self.assertLessEqual(len(res), S._MAX_LOAD_CHARS + 200)


@unittest.skipUnless(F is not None, f"文件工具依赖缺失，跳过：{_FUNC_IMPORT_ERROR}")
class TestPathGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        F.configure_path_guard([self.tmp.name])

    def tearDown(self):
        F.configure_path_guard([])
        self.tmp.cleanup()

    def test_inside_root_allowed(self):
        target = os.path.join(self.tmp.name, "a.txt")
        self.assertIsNone(F._check_path(target))

    def test_outside_root_rejected(self):
        self.assertIn("越界", F._check_path("C:\\Windows\\System32"))

    def test_delete_root_itself_rejected(self):
        self.assertIn("拒绝", F._check_destructive(self.tmp.name))

    def test_empty_path_rejected(self):
        self.assertIn("不能为空", F._check_path(""))

    def test_delete_file_inside_root(self):
        p = os.path.join(self.tmp.name, "b.txt")
        Path(p).write_text("x", encoding="utf-8")
        self.assertIn("删除成功", F.delete_file(p))


@unittest.skipUnless(F is not None, f"文件工具依赖缺失，跳过：{_FUNC_IMPORT_ERROR}")
class TestMisc(unittest.TestCase):
    def test_time_not_empty(self):
        self.assertTrue(F.get_current_time().strip())

    def test_leap_year_rule(self):
        self.assertIn("是闰年", F.is_leap_year(2024))
        self.assertIn("不是闰年", F.is_leap_year(1900))
        self.assertIn("是闰年", F.is_leap_year(2000))


if __name__ == "__main__":
    unittest.main(verbosity=2)
