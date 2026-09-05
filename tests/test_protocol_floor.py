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
  L7 §4b 目標階梯三階齊全，且第三階明文交回用戶
  L8 L7 的配對負向鎖：階梯還在但「四個計數器不得合併」的但書被刪時要紅
  L9 §4 要求「它在執行路徑上」——測試綠但沒接線不算完成

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

──────────────────────────────────────
2026-09-05 12:45 GMT+8 追加（組件 4／5 併入，v1.2.0）
──────────────────────────────────────
新增 L7／L8／L9，鎖住這次進 floor 的兩段條文（§4b 階梯、§4 的執行路徑要求）。
突變測試（唯一驗收方式，實跑輸出）：
  把 §4b 整段刪掉（522 字元）→ L7、L8 轉紅（2 failed, 7 passed）；還原 → 9 passed
  把 §4 的「在執行路徑上」那行刪掉 → L9 轉紅（1 failed, 8 passed）；還原 → 9 passed
最後執行：2026-09-05 14:59 → 9 passed ✅

⚠ 13:09 修正 L7 的假綠（抗辯發現，實跑證實）：
  原本鎖「失敗 1／2／3 次」這幾個字，但它們在 §4b 的計數器但書行也出現，
  於是**只刪掉第 2 階**（整個階梯的核心）仍然 9 passed。
  「整段刪掉會紅」不足以證明它有鑑別力——那次突變同時刪掉了兩處來源。
  改鎖各階獨有的句子後重跑同一個突變：L7 翻紅（1 failed, 8 passed）。

✅ 已驗收（本檔涵蓋）
  L1~L4、L7~L9 → 見上
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


def test_l5_evidence_clause_has_a_no_test_harness_branch(floor_text):
    """L5：§4 的證據要求必須有「專案沒有測試載體」的分支，且不得因此免除證據。

    來由：一個全新的專案通常還沒有測試套件。條文若只寫「至少一個自動化測試」，
    在那種專案上不是嚴格，是**無法執行**——而無法執行的條文會被整條略過。
    """
    assert "沒有測試載體時" in floor_text, "floor §4 缺「專案沒有測試載體」的分支"
    assert "不得因此免除證據" in floor_text, (
        "floor §4 的無測試分支被改成豁免——它該換一種證據，不是不要證據"
    )


def test_l6_failure_reporting_is_not_narrowed_to_tests(floor_text):
    """L6：§3 的「失敗照實報」不得把失敗窄化成「測試紅」。

    沒有測試的專案照樣會有紅燈（檢查、指令、建置）。窄化的措辭讓那些失敗不在射程內。
    """
    assert "測試紅就貼" not in floor_text, "floor §3 又把失敗窄化成測試紅"
    assert "紅燈就貼原始輸出" in floor_text, "floor §3 缺泛化後的失敗回報句"


def test_l7_goal_ladder_keeps_all_three_rungs(floor_text):
    """L7：§4b 的階梯三階齊全，且第三階明文交回用戶。

    來由：這條階梯的價值全在「第三次不再自己重試」。少掉任何一階，
    剩下的就只是一句鼓勵話——而 goal_gate（組件 5）機械執行的正是這三階。
    """
    assert "## 4b." in floor_text, "floor 缺 §4b 目標階梯"
    # 鎖各階**獨有**的那句話，不鎖「失敗 N 次」——那幾個字在計數器但書行也出現，
    # 於是刪掉整階仍然全綠（2026-09-05 實測：只刪第 2 階 → 9 passed，假綠）。
    rungs = {
        "第 1 階（找根因、修、重測）": "找根因、修、重測",
        "第 2 階（先跑抗辯）": "下一次動手前先跑抗辯",
        "第 3 階（停止這一項）": "停止這一項",
    }
    missing = [name for name, phrase in rungs.items() if phrase not in floor_text]
    assert not missing, f"floor §4b 缺階：{missing}"
    assert "交回用戶拍板" in floor_text, "floor §4b 第三階沒有交回用戶——變成自己無限重試"


def test_l8_the_four_counters_stay_separate(floor_text):
    """L8：L7 的配對負向鎖——階梯還在、但「不得合併」的但書被刪掉時要紅。

    四個計數器分別管方法、錯誤復發、子代理結果、目標。合併之後每一個都會提早或
    延後觸發，而合併是最省事的「簡化」，所以它需要一條專門的鎖。
    """
    assert "四個不同的計數器" in floor_text, "floor §4b 缺四計數器的區辨"
    assert "不得合併" in floor_text, "floor §4b 的「計數器不得合併」但書不見了"


def test_l9_done_requires_being_on_an_execution_path(floor_text):
    """L9：§4 必須要求「它在執行路徑上」，不是只要求它會動。

    來由：測試綠但沒接線的東西比沒做更糟——沒做的還在待辦清單上，
    已交付的會被劃掉，缺口從此無人看管。wiring_gate（組件 4）機械執行這一條。
    """
    assert "執行路徑上" in floor_text, "floor §4 缺「在執行路徑上」的完成要求"


def test_l4_progress_clause_requires_stating_a_fact(floor_text):
    """L4：L3 的配對負向鎖——光有關鍵詞不算，必須保留「已發生的事實」這個要求。

    沒有這條的話，把條文改弱成「不要寫進行中」一句口號，L3 仍會綠。
    """
    assert "已發生的事實" in floor_text, (
        "floor §3 的進度條文被改弱：只剩禁止字眼、沒有「要寫已發生的事實」的正面要求"
    )
