# -*- coding: utf-8 -*-
"""閘不得安靜地失效——本檔盯的是**根因**，不是根因的某一個實例。

驗收項目清單：
  Q1 三支 hook 的每一個 `except` 區塊，要嘛呼叫 `note_quiet`、要嘛在 `except`
     那一行標 `# quiet-ok: <理由>`；兩者皆無就紅。這是本檔存在的理由。
  Q2 `quiet-ok` 的理由不得留白——「標了但沒寫為什麼」等於沒標。
  Q3 三支各自的 `note_quiet` 行為一致（刻意保留三份副本，所以要綁在一起）。
  Q4 遙測自己壞掉不得破壞 fail-open（唯讀 `.gate_fail` 時 gate 仍正常）。
  Q5 一個標籤狂寫不得讓別的失效寫不進去（三支共用同一個檔，全域預算＝共用預算）。
  Q6 接線：屍檢必須被送進上下文——SessionStart 注入器要讀它。
  Q7 Q1 的配對：正常情況不得寫屍檢（吵到沒人看的屍檢＝沒有屍檢）。

執行命令：
  cd <repo> && python -m pytest tests/test_no_silent_gate.py -v

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-09-06 15:3x GMT+8）
══════════════════════════════════════
來由（這是本檔與其他測試檔最大的不同，寫清楚才不會被當成又一組個案測試）：

2026-09-06 一輪四鏡頭抗辯挖出 26 條缺陷。逐條修完之後回頭看，其中**約一半**是
同一個決定的不同實例：三道閘在「判不出來」時會安靜，而安靜與「一切正常」在外部
完全分不出來。

⚠ 這句話第一版寫成「幾乎全部」，逐條分類之後不成立。過度宣稱一個根因比沒找到
更糟——它會讓另一半停止被追究（另一半是：守衛斷言在自己貼的字串上、同一段邏輯
多份副本、注入內容沒有框架、機密遮蔽漏形態、註解與程式不一致，以及兩條**誤擋**）。
安靜這一類值得單獨處理的理由不是它最多，是它**唯一會再生**：其他類別修完就結案，
安靜的分支可以無限新增。

可量的證據——

  `verify_gate` 有 fail-open 屍檢（5 處）→ 本輪出 2 條缺陷
  `goal_gate`   0 處                      ┐
  `wiring_gate` 0 處                      ┘ 兩支合計出 24 條

而三支合計有 25 個 `except` 區塊，其中**只有 1 個**會留下痕跡。

所以「再跑一輪抗辯」不會收斂：每一輪找到的都是安靜的一個實例，而那個決定寫在
二十幾個地方。本檔換一個打法——不列舉實例，而是斷言**新的安靜分支不可能被加進來**：
任何人新增一個 `except`，要嘛讓它留痕，要嘛在原始碼上寫下為何不留，否則這條紅。

執行命令：python -m pytest tests/test_no_silent_gate.py -q
最後執行：2026-09-06 15:3x → 見下方實測值

[關鍵量測值]
  修法前：三支合計 25 個 except，會留痕的 1 個（verify_gate.main）
  修法後：實查 28 個 except——16 個留痕、12 個標 quiet-ok（附理由）、0 個安靜。
    ⚠ 這兩個數字第一版寫成「15／10」，與檔案對不上（2026-09-06 simplifier
    鏡頭實查指出）。在一個**專門用來防止註解與程式不一致**的檔案裡寫錯計數，
    是這一輪最該記下來的一條。修法前的「25」我核不到（那需要 git show，
    而本輪的量測是在修法後做的）→ 標 UNVERIFIED。
  雜訊控制：第一版對「repo 沒有宣告驗證指令」也留痕，一次全套測試就寫了 120 行；
    改成只記「檔案在卻讀不到」之後降到 7 行，且 7 行全部來自刻意注入失敗的測試。

✅ 已驗收（本檔涵蓋）
  Q1-Q7，全部驅動真實的 hook 檔與真實的子行程
⏳ 待驗收（本檔未涵蓋）
  「非 except 的安靜早退」（例如 `if not root: return 0`）：本檔的 AST 只掃
    例外處理。那些路徑目前靠情境測試個別覆蓋（W39／G76 等），不是通則守衛。
    解鎖條件＝需要一個能分辨「這個 return 代表放棄判定」與「這個 return 是
    正常結論」的標記方式；目前沒有，硬掃會把每個正常 return 都判成缺陷。
  屍檢被讀到之後**有沒有人處理**：Q6 只保證它進得了上下文。
"""
import ast
import io
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, ".claude", "hooks")
GATES = ("goal_gate.py", "wiring_gate.py", "verify_gate.py")
QUIET_OK_RE = re.compile(r"#\s*quiet-ok:\s*(\S.*)$")


def _source(name):
    return io.open(os.path.join(HOOKS, name), encoding="utf-8").read()


def _handlers(name):
    """回傳 [(行號, except 那一行, 區塊內是否呼叫 note_quiet)]。"""
    src = _source(name)
    lines = src.split("\n")
    out = []
    for h in ast.walk(ast.parse(src)):
        if not isinstance(h, ast.ExceptHandler):
            continue
        recorded = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "note_quiet"
            for stmt in h.body for n in ast.walk(stmt))
        raised = any(isinstance(n, ast.Raise) for stmt in h.body
                     for n in ast.walk(stmt))
        out.append((h.lineno, lines[h.lineno - 1], recorded or raised))
    return out


@pytest.mark.parametrize("gate", GATES)
def test_q1_every_except_either_records_or_says_why_not(gate):
    """Q1：每個 `except` 要嘛留痕，要嘛在原始碼上寫下為何不留。

    這是本檔的核心，也是唯一能讓這件事收斂的形態。列舉「已知的安靜分支」永遠
    追不完——2026-09-06 一輪抗辯找出 26 條，逐條修完之後第 27 條仍然可以被加進來
    而沒有人會發現。改成斷言「新的安靜分支不可能存在」之後，加一個沒有痕跡的
    `except` 就會讓這條紅，而寫下 `# quiet-ok: 理由` 是一個**必須經過思考**的動作。

    ⚠ 判準刻意接受 `raise`：把例外往上丟不是安靜，那是交給上層處理。
    """
    silent = [(n, line.strip()) for n, line, recorded in _handlers(gate)
              if not recorded and not QUIET_OK_RE.search(line)]
    assert not silent, (
        "%s 有 %d 個 except 會安靜地吞掉失敗，既沒 note_quiet 也沒 quiet-ok 標記：\n%s"
        % (gate, len(silent), "\n".join("  L%d  %s" % t for t in silent)))


@pytest.mark.parametrize("gate", GATES)
def test_q2_a_quiet_ok_marker_must_carry_a_reason(gate):
    """Q2：`quiet-ok` 標了卻沒寫理由，等於沒標。

    沒有這條，Q1 的解法就是「每個 except 後面貼一個 `# quiet-ok:`」——那會把一條
    需要思考的規則變成一個機械動作，而規則的價值全在那個思考。

    ⚠ **Q1 與 Q2 的分工不要「整理」掉**（突變實測，2026-09-06）：
      `# quiet-ok:` 後面完全空白 → 樣式根本比不中 → 由 **Q1** 判為沒有標記
      `# quiet-ok: 沒差`（有字但太短）→ 樣式比中了 → 由 **Q2** 判為理由不足
    兩條各接住一半，看起來像重複，實際上少任何一條都有一個形態會漏。
    """
    blank = [(n, line.strip()) for n, line, _ in _handlers(gate)
             if (QUIET_OK_RE.search(line)
                 and len(QUIET_OK_RE.search(line).group(1).strip()) < 8)]
    assert not blank, "%s 的 quiet-ok 沒有寫理由：%s" % (gate, blank)


def test_q3_all_three_copies_of_note_quiet_agree(tmp_path):
    """Q3：三支各自的屍檢實作行為必須一致。

    三支 hook 刻意各留一份副本（每一支都要能獨立執行，見 verify_gate 的檔頭），
    而「同一段邏輯有多份副本、守衛只跟著其中一份」正是本專案反覆再犯的類別
    ——同一天稍早 `TEST_CMD_RE` 就是這樣歪掉的，而當時綁住它的測試是取樣式的假綠。
    這裡比對**行為**（同一輸入寫出同樣格式的一行），不是取樣。

    ⚠ 三支都必須真的有 `note_quiet`，沒有 fallback。第一版寫成
    `getattr(m, 'note_quiet', None) or (lambda r: m._record_failure(r))`，
    那條 fallback 在三支都有之後**永遠不會被走到**，卻讓「少了一份」這件事
    不會紅——守衛自己開了一個後門（2026-09-06 simplifier 鏡頭指出）。
    """
    seen = {}
    for gate in GATES:
        d = tmp_path / gate
        d.mkdir()
        copy = d / gate
        copy.write_text(_source(gate), encoding="utf-8")
        code = (
            "import importlib.util;"
            "spec=importlib.util.spec_from_file_location('g',r'%s');"
            "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
            "m.note_quiet('probe', ValueError('payload-must-not-appear'))" % copy)
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             encoding="utf-8", errors="replace", timeout=60)
        assert out.returncode == 0, out.stderr
        marker = d / ".gate_fail"
        assert marker.exists(), "%s 沒有寫出屍檢檔" % gate
        line = marker.read_text(encoding="utf-8").strip()
        assert "payload-must-not-appear" not in line, (
            "%s 把例外訊息寫進去了——這個檔會被注入回對話：%s" % (gate, line))
        assert line.endswith("probe: ValueError"), line
        seen[gate] = re.sub(r"^\S+ ", "", line)
    assert len(set(seen.values())) == 1, "三支寫出的格式不一致：%s" % seen

def test_q4_broken_telemetry_does_not_break_fail_open(tmp_path):
    """Q4：遙測自己壞掉不得破壞 fail-open。

    這是屍檢這個構想唯一可能反噬的地方：為了讓失效看得見而加的東西，若自己
    會拋例外，就會把「閘安靜失效」升級成「閘弄壞 session」——比原本更糟。
    """
    copy = tmp_path / "goal_gate.py"
    copy.write_text(_source("goal_gate.py"), encoding="utf-8")
    marker = tmp_path / ".gate_fail"
    marker.mkdir()          # 讓 open(..., "a") 必定失敗（目標是目錄）
    out = subprocess.run([sys.executable, str(copy)], input="{}",
                         capture_output=True, encoding="utf-8",
                         errors="replace", timeout=60)
    assert out.returncode == 0, (
        "屍檢寫不進去就把 gate 弄掛了——fail-open 契約破了：%s" % out.stderr)


def test_q5_a_spamming_label_cannot_starve_the_others(tmp_path):
    """Q5：一個標籤狂寫，不得讓別的失效寫不進去。

    ⚠ **第一版的機制自己犯了它要治的病。** 當時是「全域 500 行、滿了停寫」，
    而三支 hook 寫的是**同一個** `.gate_fail`（都用 `dirname(__file__)`）——
    也就是三支共用一個預算。實測：`goal_gate` 壞掉、每回合寫一行，灌到 500 行
    之後 `wiring_gate` 與 `verify_gate` 的失效**永遠寫不進去，而且沒有任何訊息**。
    治療複製了它要治的病（2026-09-06 simplifier 鏡頭指出，我實測重現）。

    改成逐標籤上限之後：同一個標籤最多 `QUIET_PER_LABEL` 行，沒有全域預算，
    新的標籤永遠進得去，成長上界＝標籤數 × 上限。

    這條測試斷言的就是那個性質，不是某個數字。
    """
    copy = tmp_path / "goal_gate.py"
    copy.write_text(_source("goal_gate.py"), encoding="utf-8")
    code = (
        "import importlib.util;"
        "spec=importlib.util.spec_from_file_location('g',r'%s');"
        "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
        "[m.note_quiet('spammer', OSError()) for _ in range(600)];"
        "m.note_quiet('a quiet real failure', ValueError())" % copy)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         encoding="utf-8", errors="replace", timeout=120)
    assert out.returncode == 0, out.stderr
    body = (tmp_path / ".gate_fail").read_text(encoding="utf-8")
    lines = [ln for ln in body.splitlines() if ln.strip()]
    assert "a quiet real failure: ValueError" in body, (
        "狂寫的標籤把後來的真實失效擠掉了——那正是這個機制要治的病")
    spam = [ln for ln in lines if ln.endswith("spammer: OSError")]
    assert len(spam) <= 25, "逐標籤上限沒有生效：%d 行" % len(spam)
    assert lines[0].endswith("spammer: OSError"), "最早那一行被擠掉了"

def test_q6_the_postmortem_is_actually_surfaced(tmp_path):
    """Q6：接線——屍檢必須被送進上下文，而且要真的印出內容。

    寫下來但沒有人讀，等於沒寫，而那正是這一整條規則要修的病：`.gate_fail`
    在 `verify_gate` 裡存在了兩個月，全 repo **沒有任何東西讀它**（實查：
    除了三支 hook 自己與 CHANGELOG／reports 的敘述之外零命中）。

    ⚠ 第一版只斷言字串 `.gate_fail` 出現在注入器裡——那是「盯我貼的字串」而不是
    「盯被保護的東西」，把 `tail` 那幾行刪掉它照樣綠（2026-09-06 simplifier 指出）。
    現在真的跑那支腳本，斷言內容進得了輸出。
    """
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    for name in ("inject_protocol.sh", "fable_protocol.md"):
        src = os.path.join(HOOKS, name)
        if os.path.exists(src):
            (hooks / name).write_bytes(io.open(src, "rb").read())
    (hooks / ".gate_fail").write_text(
        "2026-09-06T00:00:00+00:00 sentinel_label: ValueError\n",
        encoding="utf-8", newline="")
    # `sh` 而不是 `bash`：本機的 `bash` 是 WSL 的，而 WSL 沒有安裝發行版，
    # 跑出來的是「請 install <Distro>」的 UTF-16 訊息。`test_wiring_gate.py`
    # 早就用 `sh`（Git 附的那支），這裡沿用同一個慣例。
    out = subprocess.run(["sh", str(hooks / "inject_protocol.sh")],
                         capture_output=True, encoding="utf-8",
                         errors="replace", timeout=60, cwd=str(tmp_path))
    assert "sentinel_label: ValueError" in out.stdout, (
        "注入器沒有把屍檢內容送進上下文——寫下來沒有人看，和沒寫一樣：\n%s"
        % out.stdout[-800:])

def test_q7_an_ordinary_run_writes_no_postmortem(tmp_path):
    """Q7：Q1 的配對——正常情況不得留痕。

    只有 Q1 的話，一個「每個 except 都記」的版本會全綠，而那會讓屍檢變成雜訊。
    實測第一版對「repo 沒有宣告 `.claude/fable-verifier`」也留痕，一次全套測試
    就寫了 **120 行**——吵到沒人看的屍檢與沒有屍檢一樣沒用，而且會把 500 行上限
    灌爆，真正的失效反而寫不進去。改成只記「檔案在卻讀不到」之後降到 7 行。
    """
    copy = tmp_path / "goal_gate.py"
    copy.write_text(_source("goal_gate.py"), encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    transcript = repo / "t.jsonl"
    transcript.write_text(json.dumps({
        "type": "user", "message": {"content": [{"type": "text", "text": "做事"}]}
    }) + "\n", encoding="utf-8", newline="")
    out = subprocess.run(
        [sys.executable, str(copy)],
        input=json.dumps({"transcript_path": str(transcript)}),
        capture_output=True, encoding="utf-8", errors="replace",
        cwd=str(repo), timeout=60)
    assert out.returncode == 0, out.stderr
    marker = tmp_path / ".gate_fail"
    assert not marker.exists(), (
        "一次完全正常的執行寫了屍檢：%s" % marker.read_text(encoding="utf-8"))
