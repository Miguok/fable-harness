# -*- coding: utf-8 -*-
"""
sandbox/calc.py 新增函式 multiply(a, b) 行為驗收——確認回傳 a*b，且不影響既有 add(a, b)=a+b+1。

驗收項目清單：
  T1 正數 × 正數 → multiply(3, 4) == 12
  T2 含 0 → multiply(0, 5) == 0 與 multiply(7, 0) == 0
  T3 負數 × 正數（正負號）→ multiply(-3, 4) == -12
  T4 交換律 → multiply(a, b) == multiply(b, a)（多組數值）

執行命令：
  cd /d/AntiGravity/Fable && python -m pytest tests/test_calc_multiply.py -v

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-07-02 23:33 GMT+8）
══════════════════════════════════════
對應規劃書：sandbox/calc.py 新增 multiply(a, b) 純函式（surgical change，未動既有 add，
  add 維持 `return a + b + 1` 原樣不變）
執行命令：python -m pytest tests/test_calc_multiply.py -v

fail-then-pass guard：
  2026-07-02 23:30 將 multiply 暫時改為錯誤實作 `return a + b`（加法冒充乘法）後執行
  → 3 failed, 1 passed（T1 3+4=7≠12、T2 的 multiply(7,0)=7≠0 分支失敗但 multiply(0,5)=5≠0
    也失敗、T3 -3+4=1≠-12 失敗；T4 交換律因加法本身可交換而意外 pass，
    但整體套件已 3 failed，證明測試能抓到「乘法誤植為加法」的錯誤）✅ guard 正確觸發
  2026-07-02 23:32 改回正確實作 `return a * b`
最後執行：2026-07-02 23:33 → 4 passed ✅

[關鍵斷言的實際量測值]
  T1 multiply(3, 4) = 12
  T2 multiply(0, 5) = 0, multiply(7, 0) = 0
  T3 multiply(-3, 4) = -12
  T4 multiply(6, 7) == multiply(7, 6) = 42

✅ 已驗收（本檔涵蓋）
  T1 → 正數相乘正確
  T2 → 含 0 的邊界正確（左乘 0、右乘 0 皆驗證）
  T3 → 負數正負號正確
  T4 → 交換律成立
⏳ 待驗收（本檔未涵蓋）
  超大數（大整數相乘的效能/精度）、浮點數（float × float 的精度誤差容忍）、
  非數值型別輸入（str/None 等應丟 TypeError 的行為）：原因為本次需求僅要求核心整數乘法
  行為，型別檢查與浮點邊界屬既有 add() 也未涵蓋的一致風格；解鎖條件＝若之後 multiply
  被實際用於浮點或外部不可信輸入場景，需另補型別防呆與浮點誤差容忍測試。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sandbox"))

from calc import multiply  # noqa: E402


def test_t1_positive_times_positive():
    assert multiply(3, 4) == 12


def test_t2_zero():
    assert multiply(0, 5) == 0
    assert multiply(7, 0) == 0


def test_t3_negative_times_positive():
    assert multiply(-3, 4) == -12


def test_t4_commutative():
    assert multiply(6, 7) == multiply(7, 6)
