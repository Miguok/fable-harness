"""兩個治理 skill 的投遞前提與零前提措辭鎖——公開可攜版。

兩件事沒有守衛就會無聲失效：

1. **frontmatter 的 description**。skill 的正文是按需載入的，而「要不要載入」完全由
   description 決定。description 寫壞或消失，skill 還在、測試還綠，但**它永遠不會被讀到**——
   這正是 N1 要修的那個病（規則沒進投遞層＝沒寫）在 skill 層的翻版。
2. **零前提措辭**。這兩份規則被改寫成「不預設專案已有測試／守衛／版控」，
   但改寫本身沒有鎖，任何人（包括我）都能無聲改回窄化版。

本檔為公開可攜測試：只讀 repo 內相對路徑，不含本機絕對路徑或私有檔假設。

驗收項目清單：
  S1 兩個 skill 各有 frontmatter，且 name 與目錄名一致
  S2 description 存在、非空，且含具體觸發時機（不是只寫「治理規則」這種泛稱）
  S3 cognitive-rubrics 的降速觸發是通則（「不需要人啟動就會跑」），不是寫死的清單
  S4 S3 的配對負向鎖：窄化版措辭不得回來
  S5 model-dispatch-rules 的證據欄與驗收欄不預設專案有測試
  S6 出界還原不預設專案有版控

執行命令：
  python -m pytest tests/test_skill_delivery.py -v

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-08-27 00:5x GMT+8）
══════════════════════════════════════
對應規劃：reports/optimization_plan_20260826.md 的 N1（投遞）與 §Z8 未修的 6 處措辭
執行命令：python -m pytest tests/test_skill_delivery.py -v
最後執行：2026-08-27 00:5x → 6 passed ✅

突變測試證據（本檔的唯一驗收方式）：
  在補本檔之前，把通則句改回「要動的是**自動執行的東西**：」→ 既有 8 個治理測試**全部照樣綠**
  （8 passed in 0.02s）——證明那 6 處改寫當時完全沒有守衛。補上本檔後同一突變會紅。
  逐條突變結果記於 commit 訊息。

✅ 已驗收（本檔涵蓋）
  S1~S6 → 見上
⏳ 待驗收（本檔未涵蓋）
  description 實際的觸發命中率：需要跨 session 統計「該載入時有沒有載入」，
  repo 目前沒有這種行為基線（解鎖條件＝建立行為驗收情境）。本檔只證明 description 存在且具體，
  不證明模型真的會在對的時機載入它。
"""

from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "skills"
GOVERNANCE_SKILLS = ("cognitive-rubrics", "model-dispatch-rules")


def _read(skill_name: str) -> str:
    path = SKILLS_DIR / skill_name / "SKILL.md"
    assert path.exists(), f"skill 不存在：{path}"
    return path.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict:
    """粗解析 YAML frontmatter；只取 key: value 的單行欄位，夠本檔用。"""
    assert text.startswith("---\n"), "缺 frontmatter——沒有 frontmatter 的 SKILL.md 不會被當成 skill"
    end = text.index("\n---", 4)
    fields = {}
    for line in text[4:end].split("\n"):
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


@pytest.mark.parametrize("skill_name", GOVERNANCE_SKILLS)
def test_s1_frontmatter_name_matches_directory(skill_name):
    """S1：name 與目錄名不一致時，slash command 與自動載入都會指錯。"""
    fields = _frontmatter(_read(skill_name))
    assert fields.get("name") == skill_name, (
        f"{skill_name}/SKILL.md 的 name 是 {fields.get('name')!r}，與目錄名不符"
    )


@pytest.mark.parametrize("skill_name", GOVERNANCE_SKILLS)
def test_s2_description_is_specific_enough_to_trigger(skill_name):
    """S2：description 是「會不會被載入」的唯一決定者，必須寫出具體觸發時機。

    只寫「治理規則」這種泛稱時，skill 存在但永遠不會被載入——
    測試照樣綠，效益卻是零。
    """
    fields = _frontmatter(_read(skill_name))
    description = fields.get("description", "")
    assert description, f"{skill_name} 缺 description——skill 不會被自動載入"
    assert "觸發時機" in description, f"{skill_name} 的 description 沒寫觸發時機"
    assert "不適用於" in description, f"{skill_name} 的 description 沒寫不適用情境（會過度觸發）"
    assert len(description) >= 60, (
        f"{skill_name} 的 description 只有 {len(description)} 字，太短不足以判斷相關性"
    )


def test_s3_slowdown_trigger_is_a_general_rule():
    """S3：降速觸發要用通則（會不會自己跑），不是寫死的工具清單。

    寫死清單的專案若沒有 CI／排程／migration，這條就對不上任何東西。
    """
    text = _read("cognitive-rubrics")
    assert "不需要人啟動就會跑" in text, "降速觸發缺通則句，退回成寫死的工具清單"
    assert "專案還沒有那些東西時" in text, "降速前置沒有「還沒有測試與契約」的分支"


def test_s4_slowdown_trigger_not_narrowed_back():
    """S4：S3 的配對負向鎖——窄化版措辭不得回來。"""
    text = _read("cognitive-rubrics")
    assert "要動的是**自動執行的東西**：" not in text, "降速觸發被改回寫死清單版"
    assert "反例：pytest 紅 →" not in text, "換路反例被改回綁死 pytest 的版本"


def test_s5_evidence_and_acceptance_do_not_assume_tests():
    """S5：派工包的驗收欄與回報模板的證據欄，都不得預設專案已經有測試。"""
    text = _read("model-dispatch-rules")
    assert "可重跑的驗證指令" in text, "回報模板的證據欄仍把證據窄化成測試命令"
    assert "證據：<測試命令" not in text, "回報模板的證據欄被改回只收測試命令"
    assert "沒有就指定別的可觀察結果" in text, "驗收標準缺「專案沒有測試」的分支"


def test_s6_out_of_scope_recovery_does_not_assume_version_control():
    """S6：出界還原的步驟不得預設專案有版控——沒有 git 時要能靠備份比對。"""
    text = _read("model-dispatch-rules")
    assert "專案有版控時用" in text, "出界還原仍寫死 git，沒有版控的專案照不了"
    assert "只還原越界的那部分" in text, "出界還原缺「不得整檔蓋回」的核心要求"
