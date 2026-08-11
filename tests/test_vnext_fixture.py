import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
MISSING_REPO = FIXTURES / "project_missing_system_repo"


class TestProjectValidatorFixture(unittest.TestCase):
    """重点项目缺失系统仓库问题的回归夹具。

    文档 3.7 指出：config 声明 `总结/系统状态仓库.md` 为唯一运行态权威，
    但实际文件不存在，同时 `总结/主角状态仓库.md` 仍保存完整系统状态。
    本夹具复现该断链，供 validate_project.py 作为确定性回归用例。
    """

    def test_fixture_config_declares_missing_system_repo(self):
        config = (MISSING_REPO / "novel-config.md").read_text(encoding="utf-8")
        self.assertIn("系统状态", config)
        self.assertFalse((MISSING_REPO / "总结" / "系统状态仓库.md").exists())

    def test_fixture_protagonist_repo_still_holds_full_system_state(self):
        repo = (MISSING_REPO / "总结" / "主角状态仓库.md").read_text(encoding="utf-8")
        self.assertIn("生存点", repo)
        self.assertIn("图纸", repo)

    def test_fixture_has_v3_manifest_and_genesis(self):
        config = (MISSING_REPO / "novel-config.md").read_text(encoding="utf-8")
        self.assertIn("schema_version：3", config)
        self.assertTrue((MISSING_REPO / "修复记录" / "生产状态" / "commit-head.json").is_file())


if __name__ == "__main__":
    unittest.main()
