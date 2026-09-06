# -*- coding: utf-8 -*-
"""整場測試的守衛：跑完之後，產品的屍檢檔不得被動過。

為什麼要放在 conftest 而不是一條普通測試：Q8 原本盯的是兩個**代理指標**
——測試模組的 `GATE` 常數不指向生產目錄、`sys.path` 不含生產目錄。兩個都是
「達成那件事的其中兩條路」，而不是那件事本身。實測第三條路（用
`importlib.util.spec_from_file_location` 直接指向生產檔）兩個指標都不碰：
全套 438 passed、Q8 3 passed，而 `.claude/hooks/.gate_fail` 實際被寫進 5 行
（2026-09-06 抗辯指出）。而且 Q8 的模組清單是寫死的三個字串，新增第四支測試
檔一樣零覆蓋——那正是同一批修法才剛在 `gate_files()` 修掉的反模式。

盯結果就沒有這個問題：不管走哪一條路、由哪一個測試檔發起，只要產品的屍檢檔
被動到，這裡就會紅。

⚠ 這條的代價：它只在**整場**結束時報告，指不出是哪一條測試寫的。那是刻意的
取捨——per-test 的快照要對每一個測試各做一次檔案 stat，而這個 repo 的全套有
四百多條。真的需要定位時，把 `--maxfail=1` 加上二分法就找得到。
"""
import os

import pytest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     ".claude", "hooks")
MARKER = os.path.join(HOOKS, ".gate_fail")


def _snapshot():
    """(存在嗎, 大小, mtime)——三者一起看，才分得出「被改過又改回來」。"""
    try:
        st = os.stat(MARKER)
        return (True, st.st_size, st.st_mtime_ns)
    except FileNotFoundError:
        return (False, 0, 0)


_BEFORE = []


def pytest_configure(config):
    """在**收集測試之前**取快照。

    ⚠ 第一版把快照放在 session fixture 的開頭，而 session fixture 最早也要等到
    第一個測試 setup 才跑——那已經在收集之後。測試模組在 **import 時**寫進產品
    屍檢檔的話（`import` 期就 `importlib` 載入生產模組並呼叫 note_quiet），
    那筆寫入已經被算進「之前」，這條守衛完全看不到：實測突變後仍 444 passed
    （2026-09-06 自查）。`pytest_configure` 早於收集，才蓋得住 import 期。
    """
    _BEFORE.append(_snapshot())


@pytest.fixture(scope="session", autouse=True)
def _production_postmortem_untouched():
    yield
    before = _BEFORE[0] if _BEFORE else _snapshot()
    after = _snapshot()
    assert after == before, (
        "整場測試動到了**產品**的屍檢檔 %s\n"
        "  之前：%s\n  之後：%s\n"
        "測試刻意注入的失敗會累積進產品自己的遙測，SessionStart 會照實喊\n"
        "「⚠ 閘曾經靜默失效（N 筆）」——假警報會訓練讀者忽略它，等於把整個\n"
        "機制廢掉。測試一律跑 gate 的副本（見 test_goal_gate.py 檔頭）。"
        % (MARKER, before, after))
