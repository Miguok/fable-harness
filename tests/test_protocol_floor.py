"""協議 floor（`.claude/hooks/fable_protocol.md`）的內容鎖——公開可攜版。

floor 是唯一每個 session 都會被注入的檔，它的條文一旦被誤刪或被改弱，
整個 kit 的行為底線就跟著消失，而且**沒有任何徵兆**——session 照樣開得起來。
本檔用整句鎖守住幾條關鍵條文。

本檔為公開可攜測試：只讀 repo 內的相對路徑，不含任何本機絕對路徑或私有檔假設。

驗收項目清單：
  L1 floor 含協議代號（缺了代表注入的不是這份協議）
  L2 五大節標題齊全（OODA／抗辯／回報紀律／完成定義／模型分工）
  L3 §3 的「沒有進行中」整句在位——狀態只能報已完成／未開始
  L4 L3 的配對負向鎖：只寫關鍵詞而缺少「已發生的事實」這個要求時要紅
     （防止把條文改弱成一句口號後測試照樣綠）

執行命令：
  python -m pytest tests/test_protocol_floor.py -v

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-08-26 14:1x GMT+8）
══════════════════════════════════════
對應規劃：reports/optimization_plan_20260826.md 的 F5（§3 收工自檢消歧）與 N4（公開可攜測試）
執行命令：python -m pytest tests/test_protocol_floor.py -v
最後執行：2026-08-26 14:1x → 4 passed ✅

突變測試證據（本檔的唯一驗收方式，實跑輸出見下方 commit 訊息）：
  把 §3 那一整行從 floor 刪掉 → L3、L4 轉紅；還原 → 4 passed。
  「現在是綠的」不構成證據，會歸零才是。

✅ 已驗收（本檔涵蓋）
  L1~L4 → 見上
⏳ 待驗收（本檔未涵蓋）
  條文能否真的改變模型行為：需要改前／改後的固定任務情境與成功率，
  repo 目前沒有這種行為基線（解鎖條件＝建立行為驗收情境，對應計畫 §Z3-1）。
  本檔只證明「文字還在且沒被改弱」，不證明「行為變好」。
"""

from pathlib import Path

import pytest

FLOOR = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "fable_protocol.md"

SECTION_TITLES = [
    "## 1. OODA",
    "## 2. 多方抗辯",
    "## 3. 回報紀律",
    "## 4. 完成定義",
    "## 5. 模型分工",
]


@pytest.fixture(scope="module")
def floor_text() -> str:
    assert FLOOR.exists(), f"floor 不存在：{FLOOR}"
    return FLOOR.read_text(encoding="utf-8")


def test_l1_floor_carries_protocol_codename(floor_text):
    """L1：缺了代號，就無法確認 session 注入的是這份協議。"""
    assert "FABLE-PROTOCOL-V1-CANARY" in floor_text, "floor 缺協議代號"


def test_l2_all_five_sections_present(floor_text):
    """L2：五大節任一消失＝該層底線整段不見。"""
    missing = [t for t in SECTION_TITLES if t not in floor_text]
    assert not missing, f"floor 缺節：{missing}"


def test_l3_progress_has_no_in_progress_state(floor_text):
    """L3：§3 必須明文禁止用「進行中」當狀態值。

    來由：回覆送出的當下沒有任何東西在跑，寫「進行中」是把計畫講成事實。
    """
    assert "沒有「進行中」" in floor_text, "floor §3 缺「沒有進行中」的整句鎖"
    assert "已完成／未開始" in floor_text, "floor §3 缺「只用已完成／未開始兩個值」的要求"


def test_l4_progress_clause_requires_stating_a_fact(floor_text):
    """L4：L3 的配對負向鎖——光有關鍵詞不算，必須保留「已發生的事實」這個要求。

    沒有這條的話，把條文改弱成「不要寫進行中」一句口號，L3 仍會綠。
    """
    assert "已發生的事實" in floor_text, (
        "floor §3 的進度條文被改弱：只剩禁止字眼、沒有「要寫已發生的事實」的正面要求"
    )
