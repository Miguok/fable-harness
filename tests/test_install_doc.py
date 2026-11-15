"""INSTALL.md 的解除安裝步驟必須涵蓋安裝時複製到 ~/.claude 的每一個東西——公開可攜測試。

一句話目的：安裝清單與解除安裝清單是兩份手寫文字，沒有守衛就會漂移。1.8.1 之前
  INSTALL.md 步驟 8 複製三個 skill，Uninstall 卻只刪 adversarial-review，另外兩個留在
  ~/.claude/skills/ 繼續載入、繼續指向一個已不再注入的協議。

驗收項目清單：
  U1 scripts/fable_doctor.py 的 COPIED_ARTIFACTS（複製到 ~/.claude 的唯一清單）裡每一項，
     它在 ~/.claude 下的位置（skill 取目錄、agent 取檔名）都出現在 INSTALL.md 的 Uninstall 一節
  U2 repo 裡 .claude/skills/ 下的每個 skill 目錄與 .claude/agents/ 下的每個 agent，
     都在 COPIED_ARTIFACTS 裡（否則 U1 的清單本身就漏了，doctor 的漂移檢查也看不到）
  U3 配對：Uninstall 一節找得到（標題改名會讓 U1 讀到空字串而假綠）

本檔為公開可攜測試：只讀 repo 內相對路徑，不含本機絕對路徑或私有檔假設。

執行命令：
  python -m pytest tests/test_install_doc.py -v

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-11-15 18:4x GMT+8）
══════════════════════════════════════
對應：1.8.2 Fixed「解除安裝漏刪兩個治理 skill」
執行命令：python -m pytest tests/test_install_doc.py -v
最後執行：見 1.8.2 發佈的 commit 訊息（先紅：修 INSTALL.md 之前 U1 兩案失敗；後綠：修之後全過）

✅ 已驗收（本檔涵蓋）
  U1 → 6 個複製品的位置都在 Uninstall 一節
  U2 → repo 的 skill／agent 都在 COPIED_ARTIFACTS
  U3 → Uninstall 一節存在且非空
⏳ 待驗收（本檔未涵蓋）
  Uninstall 寫的刪除動作是否真的把東西刪乾淨：那是使用者手動執行的文件步驟，repo 沒有
  模擬家目錄的端到端解除安裝。解鎖條件：若日後有 uninstall 腳本，改測腳本本身。
"""
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _copied_artifacts():
    spec = importlib.util.spec_from_file_location("fable_doctor_for_doc_test", ROOT / "scripts" / "fable_doctor.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.COPIED_ARTIFACTS)


def _uninstall_section():
    text = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
    m = re.search(r"^## Uninstall\s*$(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1) if m else ""


def _installed_location(artifact):
    """.claude/skills/<name>/SKILL.md → ~/.claude/skills/<name>/；.claude/agents/<x>.md → <x>.md"""
    parts = artifact.parts
    if parts[1] == "skills":
        return "~/.claude/skills/%s/" % parts[2]
    return parts[-1]


def test_u3_uninstall_section_exists():
    assert _uninstall_section().strip(), "INSTALL.md 找不到 `## Uninstall` 一節，或它是空的"


@pytest.mark.parametrize("artifact", _copied_artifacts(), ids=lambda p: p.as_posix())
def test_u1_uninstall_covers_every_copied_artifact(artifact):
    where = _installed_location(artifact)
    assert where in _uninstall_section(), (
        "INSTALL.md 的 Uninstall 沒提到 %s——安裝會複製它，解除安裝卻會把它留在 ~/.claude" % where)


def test_u2_every_repo_skill_and_agent_is_a_copied_artifact():
    listed = {p.as_posix() for p in _copied_artifacts()}
    repo = [p.relative_to(ROOT).as_posix() for p in (ROOT / ".claude" / "skills").glob("*/SKILL.md")]
    repo += [p.relative_to(ROOT).as_posix() for p in (ROOT / ".claude" / "agents").glob("*.md")]
    missing = sorted(set(repo) - listed)
    assert not missing, "這些在 repo 裡、卻不在 fable_doctor 的 COPIED_ARTIFACTS：%s" % missing
