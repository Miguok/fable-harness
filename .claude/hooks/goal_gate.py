# -*- coding: utf-8 -*-
"""Goal gate（FABLE-PROTOCOL 組件 5）——第三階：接了線，但目標還是沒達成。

一句話：同一個目標連續失敗到一定次數時，強制換打法，最後強制擱置並交回用戶。

三階同一把尺，本檔是最後一階：
  1. 改了程式碼卻沒跑測試              → verify_gate（組件 3）
  2. 測試綠了但那東西不在執行路徑上    → wiring_gate（組件 4）
  3. 接上了、也跑了，但目標就是沒達成  → 本檔

為什麼要有機械化的第三階——失敗第一次會找根因，第二次會再找一次，
第三次開始就是**同一套思路換皮重試**，而重試的成本是線性的、
「這次應該就對了」的錯覺卻是恆定的。文字規則擋不住它：
`cognitive_rubrics.md` 早就寫了「同一方法連續失敗 2 次就換路」，
而它管的是**方法**；本檔管的是**目標**，兩個計數器刻意分開
（該檔第 13/35/45 行明令三個計數器不得合併，本檔是第四個）。

階梯（門檻可調，見下方 env）：
  連續失敗 1 次 → 不介入。找根因、修、重測，那是正常工作。
  連續失敗 2 次 → 擋一次收工：**下一次動手前先跑抗辯**（adversarial-review），
                  因為第二次沒中，代表根因判定本身可能就是錯的。
  連續失敗 3 次 → 擋一次收工並**自動寫入擱置清單**：停止這一項，
                  交回用戶拍板，改做不相關的項目。
  任何一次測試全綠 → 計數歸零。

用戶回來時：`UserPromptSubmit` 會把擱置清單注入；若清單非空而這一輪
從頭到尾沒提到它，`Stop` 會擋一次，確保它真的被講出來而不是靜靜躺著。

擱置項由本 gate **自動建立**（含當時的失敗指令與時間），不依賴我記得去寫——
「靠人記得」正是這三階要消滅的東西。

狀態檔：<repo>/.fable/goal_state.json（本機用，建議 gitignore）。
介面：stdin 收 hook JSON；stdout 輸出 block JSON 或無輸出。
      任何錯誤一律 fail-open（exit 0 無輸出）——gate 絕不可弄壞 session。
測試：tests/test_goal_gate.py（fail-then-pass + 突變已驗證）。
"""
import json
import os
import re
import subprocess
import sys
import time

SHELL_TOOLS = {"Bash", "PowerShell"}

# 與 verify_gate 相同的測試指令辨識範圍（那裡是唯一正本；此處只需知道
# 「這條指令是不是一次測試執行」，故取其交集的常見形態）。
TEST_CMD_RE = re.compile(
    r"(pytest"
    r"|python[3]?(\.exe)?\s+(-m\s+unittest|(\S*[/\\])?(test\S*\.py|\S*_test\.py))"
    r"|npm\s+(run\s+)?test\b|yarn\s+test\b|pnpm\s+(run\s+)?test\b|bun\s+test\b|node\s+--test"
    r"|go\s+test|cargo\s+test|\bvitest\b|\bjest\b"
    r"|mvnw?(\.cmd)?\s+(\S+\s+)*test(\s|$)|gradlew?(\.bat)?\s+(\S+\s+)*test(\s|$)"
    r"|dotnet\s+test(\s|$)|\brspec\b|\bphpunit\b|\bctest\b|make\s+test\b"
    r"|rake\s+(\S+\s+)*test\b|mix\s+test\b|\s--test(\s|$))"
)

# 測試摘要行：`12 passed in 1.2s`／`1 failed, 11 passed`／`3 errors in 0.5s`。
# 一段輸出裡可能有很多條（一個 shell 呼叫跑好幾次測試）；**最後一條**才是終局狀態。
SUMMARY_LINE = re.compile(
    r"^.*\b[0-9]+\s+(?:passed|failed|errors?)\b.*$", re.M)
COUNT_FAIL_IN_SUMMARY = re.compile(r"\b[1-9][0-9]*\s+(?:failed|errors?)\b")
# 軟性標記：在**通過**的執行裡也會出現（捕捉到的日誌、斷言會拋例外的測試、docstring 內文）。
# 只有在完全沒有摘要行時才拿來判斷。
# 「跑了但一條測試都沒跑到」：pytest 過濾光了、路徑打錯、全部 skip，
# 以及**測試工具根本沒跑起來**（沒裝、拼錯指令）——那同樣不是一次測試執行，
# 當成通過會把連敗數清掉。只認 pytest 的說法就只擋得住被舉例的那一種。
NOTHING_RAN = re.compile(
    r"\bno tests ran\b|\bcollected 0 items\b|(?<![0-9])0 passed\b"
    r"|\bNo module named\b|\bModuleNotFoundError\b"
    r"|\bcommand not found\b|\bis not recognized as\b", re.I)
SOFT_FAIL_MARKERS = (
    re.compile(r"^FAILED\s", re.M),
    re.compile(r"\bAssertionError\b"),
    re.compile(r"^E\s+\w+Error", re.M),
)

ADVERSARIAL_AT = int(os.environ.get("FABLE_GOAL_ADVERSARIAL_AT", "2"))
SHELVE_AT = int(os.environ.get("FABLE_GOAL_SHELVE_AT", "3"))
STATE_REL = os.path.join(".fable", "goal_state.json")


# ── transcript ────────────────────────────────────────────────────────────
LOCAL_COMMAND_PREFIXES = (
    "<command-name>", "<local-command-stdout>",
    "<local-command-stderr>", "<local-command-caveat>",
)


def is_real_user_prompt(entry):
    if entry.get("type") != "user":
        return False
    content = entry.get("message", {}).get("content")
    if not isinstance(content, str):
        return False
    return not content.lstrip().startswith(LOCAL_COMMAND_PREFIXES)


def load_entries(path):
    entries = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def current_turn(entries):
    last = -1
    for i, e in enumerate(entries):
        if is_real_user_prompt(e):
            last = i
    return entries[last + 1:]


def _result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            c.get("text", "") for c in content
            if isinstance(c, dict) and c.get("type") == "text")
    return ""


# 也要吃掉重導向前面的檔案描述元（`2>&1` 的那個 2），否則它會留在鍵尾。
PIPELINE_TAIL_RE = re.compile(r"\s*[0-9]?\s*[|>].*$", re.S)


def test_key(command):
    """The identity of a test run, with the shell plumbing removed.

    `pytest x.py | tail -4` and `pytest x.py | tail -2` are the same run looked
    at through different windows, but keyed on the raw string they are two
    targets — so a red one never gets a green from its twin and the streak
    ratchets. Observed twice on this gate's own author (2026-09-05): a genuinely
    failing run, fixed, then re-run with a different `tail` count.

    The same applies to what comes *before* it. `cd x && sed -i … && pytest t.py`
    and a bare `pytest t.py` are one target reached twice, and keying on the
    whole line put the red one and the green one under different keys — the
    streak then never cleared. Observed a third time on this gate's own author
    (2026-09-05), after the pipeline-suffix fix had already landed.

    This honours what the per-command rule was written for — "the last result of
    each distinct test command" — rather than changing it: neither the shell
    plumbing around a test run nor the window you view it through is part of the
    test command.
    """
    stripped = PIPELINE_TAIL_RE.sub("", command)
    m = TEST_CMD_RE.search(stripped)
    if m:
        stripped = stripped[m.start():]
    return " ".join(stripped.split())


def _verdict(text):
    """Classify one tool result as "fail", "pass" or "vacuous".

    The unit is the last summary line, not "is there a failure anywhere in
    here". One shell invocation routinely contains several test runs — mutation
    testing is written that way by construction: break it, run (red), restore,
    run (green), all in one script, arriving as a single tool result with the
    outputs concatenated. Keying on the command string cannot split that, so the
    only honest reading of a concatenated output is where it ended up.

    Observed twice on this gate's own author (2026-09-05), both times on
    mutation runs of a guard that was working correctly. The first fix assumed
    one command equals one run; this one drops that assumption.

    When there is no summary line at all, fall back to the soft markers
    ("AssertionError", "FAILED ...") — those also occur in passing runs, in
    captured logs and in tests asserting that something raises, so they only
    decide when nothing better is available.

    Erring toward "not failed" is deliberate. A false positive makes the gate
    fire during normal work, and a gate that nags gets bypassed — a bypassed
    gate is worth nothing. A false negative merely delays it one turn.

    "vacuous" is the third answer: `pytest -k nomatch` prints `no tests ran`
    and exits 0, and counting that as a pass cleared the streak, so a ladder at
    strike 1 dropped back to 0 and never reached the review rung. It is judged
    on the same last-summary-line unit as the other two — reading "nothing ran"
    from anywhere in the output made `[wiring] no tests ran` followed by
    `12 passed` vacuous, which stopped a genuine green from clearing anything.
    """
    summaries = SUMMARY_LINE.findall(text)
    if summaries:
        last = summaries[-1]
        if COUNT_FAIL_IN_SUMMARY.search(last):
            return "fail"
        return "vacuous" if NOTHING_RAN.search(last) else "pass"
    if NOTHING_RAN.search(text) or not text.strip():
        return "vacuous"
    return "fail" if any(p.search(text) for p in SOFT_FAIL_MARKERS) else "pass"


def analyze_turn(turn):
    """Return (test_ran, test_failed, last_test_command).

    A turn counts as failed only when a test actually ran AND its output
    carries an unambiguous failure marker. Silence is not failure.
    """
    test_ids, commands = {}, {}
    for e in turn:
        if e.get("type") != "assistant":
            continue
        content = e.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            if b.get("name") not in SHELL_TOOLS:
                continue
            cmd = (b.get("input") or {}).get("command", "")
            if TEST_CMD_RE.search(cmd):
                test_ids[b.get("id")] = True
                commands[b.get("id")] = cmd

    if not test_ids:
        return False, False, ""

    # Per test command, keep only its LAST result in this turn.
    #
    # Not "did anything fail here" — that reading fires on the two practices the
    # protocol itself mandates, both of which are red-then-green by construction:
    # mutation testing (break it on purpose, watch the guard flip, restore) and
    # fail-then-pass evidence. Counting those as failed attempts would penalise
    # exactly the work that proves a fix is real. Observed 2026-09-05, on this
    # gate's own author, within an hour of shipping it.
    #
    # Per command rather than "the last run in the turn": otherwise any quick
    # green run afterwards would mask a target that is genuinely still red.
    last_by_cmd = {}
    raw_by_key = {}
    for e in turn:
        if e.get("type") != "user":
            continue
        content = e.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict) or b.get("type") != "tool_result":
                continue
            tid = b.get("tool_use_id")
            if tid not in test_ids:
                continue
            raw = commands.get(tid, "")
            key = test_key(raw)
            last_by_cmd[key] = _verdict(_result_text(b))
            # 鍵是用來「認出同一個目標」的，回報時要給的是使用者實際下的那條指令：
            # 擱置紀錄的用途就是讓人看出當時卡在哪，存截短過的鍵等於把它丟掉。
            raw_by_key[key] = raw

    # A run that reported no result at all is dropped rather than counted as a
    # pass: otherwise one filtered-out pytest between two real failures resets
    # the ladder, and the second rung is never reached.
    verdicts = {c: v for c, v in last_by_cmd.items() if v != "vacuous"}
    if not verdicts:
        return False, False, ""
    still_red = [c for c, v in verdicts.items() if v == "fail"]
    return True, bool(still_red), raw_by_key.get(still_red[-1], "") if still_red else ""


# ── state ─────────────────────────────────────────────────────────────────
def repo_root():
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
    except Exception:
        return None
    root = r.stdout.strip()
    return root if r.returncode == 0 and root else None


def state_path(root):
    return os.path.join(root, STATE_REL)


def load_state(root):
    """Return the state, or None when the file is there but cannot be read.

    None means **do not touch it**. Returning an empty state for an unreadable
    file looks harmless until the next write: `save_state` replaces the whole
    file, so a truncated or locked state file (a parallel session, a scanner
    holding it open, a full disk) silently discarded the entire shelf —
    including notes a person had written by hand. Observed 2026-09-05.

    A *missing* file is a different thing and stays a fresh start.
    """
    p = state_path(root)
    if not os.path.exists(p):
        return {"streak": 0, "shelved": []}
    try:
        with open(p, encoding="utf-8") as fh:
            s = json.load(fh)
    except Exception:
        return None
    if not isinstance(s, dict):
        return None
    s.setdefault("streak", 0)
    s.setdefault("shelved", [])
    return s


# 看起來像機密的鍵名。遮蔽的對象是**鍵名**而不是所有 `=`：把每個 `key=value`
# 都遮掉會讓 `make test FILE=tests/test_auth.py CASE=login` 變成
# `FILE=*** CASE=***`——擱置項的用途正是讓人認出「當時卡在哪」，遮到認不出來
# 就把這條記錄變成廢話。
SECRET_KEY = r"[\w.-]*(?:token|secret|password|passwd|pass|apikey|api_key|key|auth|credential|cred)"
SECRET_ASSIGN_RE = re.compile(r"(?i)\b(-{0,2}" + SECRET_KEY + r")=(\S+)")
SECRET_SPACED_RE = re.compile(r"(?i)(\s--?" + SECRET_KEY + r")\s+(\S+)")
# URL 內嵌帳密：`postgres://user:pw@host/db`。
URL_CRED_RE = re.compile(r"(://[^:/\s]+):([^@/\s]+)@")


def redact(command):
    """Mask secret-looking values before a command is stored or echoed.

    The command is written to a file inside the user's repository and read back
    into the conversation on the next turn, and `TOKEN=… pytest` matches the
    test-command pattern like anything else. Three shapes are covered: an
    assignment whose key looks like a credential (in any position, not only the
    leading env prefix), the same key given as a spaced flag (`--token abc`),
    and credentials embedded in a URL.

    Keys that do not look like credentials keep their values: a shelf entry
    exists to show what you were stuck on, and `FILE=tests/test_auth.py`
    masked into `FILE=***` throws that away to buy nothing.
    """
    out = SECRET_ASSIGN_RE.sub(r"\1=***", command)
    out = SECRET_SPACED_RE.sub(r"\1 ***", out)
    return URL_CRED_RE.sub(r"\1:***@", out)


def save_state(root, state):
    p = state_path(root)
    d = os.path.dirname(p)
    os.makedirs(d, exist_ok=True)
    # Self-ignoring directory: the state holds the user's failing commands, and
    # it lands in *their* repo. Telling them to add `.fable/` to .gitignore
    # (INSTALL step 11) only works if they read that step — a repo with no
    # .gitignore at all would commit it on the next `git add -A`.
    marker = os.path.join(d, ".gitignore")
    if not os.path.exists(marker):
        with open(marker, "w", encoding="utf-8", newline="") as fh:
            fh.write("*\n")
    # PID in the temp name: two sessions in one repo writing `goal_state.json.tmp`
    # at the same time would have one clobber the other mid-write.
    tmp = "%s.tmp.%d" % (p, os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, p)
    except OSError:
        # Read-only file, a scanner holding it open, a full disk. Leaving the
        # temp file behind would accumulate one per process id, invisible
        # because this directory ignores itself.
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False
    return True


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


# ── the two entry points ──────────────────────────────────────────────────
def run_stop(data, root):
    entries = load_entries(data["transcript_path"])
    turn = current_turn(entries)
    ran, failed, cmd = analyze_turn(turn)
    cmd = redact(cmd)
    state = load_state(root)
    if state is None:
        # Say so. Refusing to overwrite protects the data, but staying silent
        # about it would leave the whole component switched off with nobody
        # aware — the exact silent failure this ladder exists to remove.
        block(
            f"⛔ FABLE goal gate: {STATE_REL} exists but cannot be read as JSON.\n\n"
            "Nothing was written — the file is left exactly as it is, in case it still "
            "holds shelved items with notes. Until it parses, this gate is doing nothing "
            "at all: no counting, no shelving, no reminders.\n\n"
            "Repair the JSON, or delete the file to start a fresh streak (deleting loses "
            "any shelved items it still holds)."
        )
        return 0

    if ran and not failed:
        # A green run clears the streak. This is the only way out other than
        # shelving — otherwise the counter would ratchet forever and the gate
        # would eventually fire on unrelated work.
        if state["streak"]:
            state["streak"] = 0
            save_state(root, state)

    if ran and failed:
        state["streak"] += 1
        streak = state["streak"]

        if streak == ADVERSARIAL_AT:
            save_state(root, state)
            block(
                f"⛔ FABLE goal gate: this goal has now failed {streak} times in a row.\n\n"
                f"Last failing command:\n  {cmd}\n\n"
                "Two failures means the root cause you identified is probably not the root "
                "cause. A third attempt built on the same reading of the problem is the same "
                "attempt wearing different clothes.\n\n"
                "Before the next attempt, run the adversarial review (skeptic / red-team / "
                "simplifier, in one message) against your current root-cause claim, and say "
                "which of the three lenses survived. Then attempt again.\n\n"
                "If you have already done that this turn, end the turn again and this will "
                "let you through."
            )
            return 0

        if streak >= SHELVE_AT:
            item = {
                "id": f"goal-{int(time.time())}",
                "first_seen": time.strftime("%Y-%m-%d %H:%M:%S"),
                "streak": streak,
                "last_command": cmd,
                "note": "",
            }
            # The gate writes the shelf entry itself. Relying on the agent to
            # remember to write it is exactly the failure this ladder exists
            # to remove.
            state["shelved"].append(item)
            state["streak"] = 0
            save_state(root, state)
            block(
                f"⛔ FABLE goal gate: {streak} consecutive failures on this goal — shelving it.\n\n"
                f"Last failing command:\n  {cmd}\n\n"
                f"Shelved as {item['id']} in {STATE_REL}.\n\n"
                "Stop working this item. Three attempts without reaching the goal means the "
                "problem is not what you think it is, and further attempts spend the user's "
                "budget to confirm that.\n\n"
                "Do this instead:\n"
                "  1. Write one paragraph into the shelf entry's \"note\": what you tried, what "
                "     the evidence actually says, and the specific question the user has to "
                "     answer for this to move.\n"
                "  2. Tell the user it is shelved and why — plainly, without burying it.\n"
                "  3. Move on to items in the queue that do not depend on this one.\n\n"
                "The shelf is surfaced to you again the moment the user returns."
            )
            return 0

        save_state(root, state)
        return 0

    # Nothing failed this turn. A shelved item whose `note` is still empty has
    # not been explained to anyone yet — block until it is.
    #
    # The trigger is the empty note, and *only* the empty note — not "this turn
    # didn't mention it". Mentioning the id used to be enough, which made §4b's
    # own instruction ("raise the shelved items when the user returns") the
    # unlock code: say the id, gate satisfied, note never written. Writing the
    # note is a one-time act that ends the blocking permanently, which is what
    # makes it enforceable without turning into a nag.
    unexplained = [i for i in state["shelved"] if not i.get("note")]
    if unexplained:
        block(
            "⛔ FABLE goal gate: shelved items with no explanation recorded.\n\n"
            + "\n".join(
                f"  {i.get('id', '?')}  ({i.get('first_seen', '?')})  "
                f"{i.get('last_command', '')[:80]}"
                for i in unexplained)
            + "\n\nA shelved item nobody explained is indistinguishable from an abandoned "
              f"one. Fill in \"note\" for each entry in {STATE_REL} — what you tried, what "
              "the evidence says, and the specific question the user must answer — then say "
              "so to the user and end the turn again.\n\n"
              "Delete an entry once it is resolved or the user drops it."
        )
    return 0


def run_prompt(root):
    """UserPromptSubmit: the user is back — put the shelf in front of them."""
    state = load_state(root)
    if state is None or not state["shelved"]:
        return 0
    lines = [
        "【FABLE goal gate — items shelved awaiting the user's decision】",
        "",
    ]
    for i in state["shelved"]:
        # `.get` throughout: the block message tells the user to hand-edit this
        # file to fill in `note`, and a hand edit that drops a key would
        # otherwise raise, get swallowed by the fail-open, and take the whole
        # shelf out of sight — the gate's own instruction breaking the gate.
        lines.append(f"- {i.get('id', '?')}  (shelved {i.get('first_seen', '?')}, "
                     f"after {i.get('streak', '?')} failures)")
        lines.append(f"    last failing command: {i.get('last_command', '')[:160]}")
        if i.get("note"):
            lines.append(f"    note: {i['note']}")
    lines += [
        "",
        "These stopped because three attempts did not reach the goal, not because they were",
        "forgotten. Raise them with the user now rather than resuming them silently. Remove an",
        f"entry from {STATE_REL} once it is resolved or the user drops it.",
    ]
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "\n".join(lines)}}, ensure_ascii=False))
    return 0


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
        root = repo_root()
        if not root:
            return 0
        event = data.get("hook_event_name") or ""
        if event == "UserPromptSubmit" or "--prompt" in sys.argv:
            return run_prompt(root)
        if data.get("stop_hook_active"):
            return 0  # never deadlock: the second attempt always goes through
        if not data.get("transcript_path"):
            return 0
        return run_stop(data, root)
    except Exception:
        return 0  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
