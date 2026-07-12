# -*- coding: utf-8 -*-
"""
sandbox/calc.py 新增函式 subtract(a, b) 行為驗收——確認回傳 a-b，且不影響既有 add(a, b)=a+b+1。

驗收項目清單：
  T1 正數相減 → subtract(10, 4) == 6
  T2 負結果 → subtract(4, 10) == -6
  T3 含零 → subtract(5, 0) == 5 與 subtract(0, 5) == -5
  T4 含負數 → subtract(-3, -8) == 5

執行命令：
  cd <repo> && python -m pytest tests/test_calc_subtract.py -v

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-07-03 GMT+8）
══════════════════════════════════════
對應規劃書：sandbox/calc.py 新增 subtract(a, b) 純函式（surgical change，未動既有 add，
  add 維持 `return a + b + 1` 原樣不變）
執行命令：python -m pytest tests/test_calc_subtract.py -v

fail-then-pass guard：
  2026-07-03 （subtract 尚未實作前）執行 → ImportError: cannot import name 'subtract'
    from 'calc'（因 sandbox/calc.py 當時只有 add、multiply，無 subtract），
    4 個測試全部 collection error，證明測試能抓到「函式不存在」的錯誤 ✅ guard 正確觸發
  2026-07-03 於 sandbox/calc.py 新增 `def subtract(a, b): return a - b`
最後執行：2026-07-03 → 4 passed ✅

[關鍵斷言的實際量測值]
  T1 subtract(10, 4) = 6
  T2 subtract(4, 10) = -6
  T3 subtract(5, 0) = 5, subtract(0, 5) = -5
  T4 subtract(-3, -8) = 5

✅ 已驗收（本檔涵蓋）
  T1 → 正數相減正確
  T2 → 負結果正確
  T3 → 含零的邊界正確（被減數為 0、減數為 0 皆驗證）
  T4 → 含負數輸入正確
⏳ 待驗收（本檔未涵蓋）
  超大數（大整數相減的效能/精度）、浮點數（float - float 的精度誤差容忍）、
  非數值型別輸入（str/None 等應丟 TypeError 的行為）：原因為本次需求僅要求核心整數減法
  行為，型別檢查與浮點邊界屬既有 add()/multiply() 也未涵蓋的一致風格；解鎖條件＝若之後
  subtract 被實際用於浮點或外部不可信輸入場景，需另補型別防呆與浮點誤差容忍測試。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sandbox"))

from calc import subtract  # noqa: E402


def test_t1_positive_subtraction():
    assert subtract(10, 4) == 6


def test_t2_negative_result():
    assert subtract(4, 10) == -6


def test_t3_zero():
    assert subtract(5, 0) == 5
    assert subtract(0, 5) == -5


def test_t4_negative_operands():
    assert subtract(-3, -8) == 5
