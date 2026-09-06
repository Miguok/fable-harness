# -*- coding: utf-8 -*-
"""發佈交易——本 kit 唯一支援的發佈路徑。

一句話：發佈不是一條指令，是一筆**交易**；它的前置條件裡有「這個 commit
已經被抗辯審查過」，沒有它就完成不了。

為什麼不做成「攔 `gh release create` 的 hook」
────────────────────────────────────────────
協議 §2 早就寫了「對外發佈前必須抗辯」，而 1.4.1 與 1.4.2 的 CHANGELOG 逐字
記載：規則的作者在同一天跳過它兩次，兩次都是發佈之後才補審查，而那些審查
真的找出了缺陷。所以「文字規則」這一層已經被證明不夠。

但**攔指令是錯的攔法**。`gh release create`、`git push --tags`、`git tag`、
直接打 GitHub API、網頁介面——這是一個無限的語法面，接線閘門已經在
`--no-verify` 上證明過這條路要一直追。穩定的是另一件事：**產出物本身的
前置條件**。所以這裡不猜使用者怎麼下指令，而是讓「發佈」這個動作只有一條
路走得通，而那條路上有一道必經的檢查。

證據必須綁 commit（TOCTOU）
────────────────────────────
只要求「存在一份抗辯審查」不夠：審查完再改一行程式，舊審查照樣可以拿來發
新內容。所以 attestation 記的是 `reviewed_commit`，而發佈時要求
`reviewed_commit == HEAD == tag 指向的 commit`，三者一致才放行。

緊急出口（break-glass）
────────────────────────
`--override-review --reason "…"` 可以跳過審查檢查，但**必須留痕**：理由會被
寫進 attestation 紀錄與發佈說明，發佈紀錄上會標明「本版未經抗辯審查」。
保留它的理由是：沒有緊急出口時，真正緊急的人會發明更髒的旁路，而那些旁路
不會留下任何紀錄。這不是漏洞，是一條有記錄的破窗通道。

介面：
  python scripts/release.py --check            只跑前置條件，不發佈
  python scripts/release.py --attest --lenses "skeptic:REFUTED,…"
  python scripts/release.py 1.5.0              跑完前置條件並建立 tag + Release
  python scripts/release.py 1.5.0 --override-review --reason "…"

測試：tests/test_release_gate.py
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATTEST_DIR = os.path.join(ROOT, ".fable", "attestations")
VERSION_FILE = os.path.join(ROOT, "VERSION")
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")
LENS_NAMES = ("skeptic", "red-team", "simplifier")


def run(args, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("encoding", "utf-8")
    kw.setdefault("errors", "replace")
    kw.setdefault("cwd", ROOT)
    kw.setdefault("timeout", 300)
    try:
        return subprocess.run(args, **kw)
    except (OSError, subprocess.SubprocessError) as e:  # quiet-ok: 轉成 rc=127 交給呼叫端，前置條件會把它印出來
        # 執行檔不存在時 subprocess 拋的是例外而不是非零退出。讓呼叫端一律
        # 只需要看 returncode，否則「gh 沒裝」會變成一個沒人接的 traceback。
        return subprocess.CompletedProcess(args, 127, "", str(e))


def head_commit():
    out = run(["git", "rev-parse", "HEAD"])
    return (out.stdout or "").strip() if out.returncode == 0 else ""


def attestation_path(commit):
    return os.path.join(ATTEST_DIR, "%s.json" % commit)


def read_attestation(commit):
    try:
        with open(attestation_path(commit), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):  # quiet-ok: 回 None 讓 check_review 大聲說「沒有審查紀錄」並擋下發佈
        return None
    # 合法 JSON 但不是物件（`[]`、`"x"`、`null`）會讓下游的 `doc.get` 拋
    # AttributeError——實測 `printf '[]' > .fable/attestations/<HEAD>.json`
    # 之後 `--check` 直接 traceback。方向是 fail-closed（發佈中止），但
    # goal_gate 的 load_state 早就對同一件事驗了 `isinstance(s, dict)`，
    # 而這道閘的文案同樣叫人手動編 `.fable/`：同一類沒掃到第二個寫入者。
    return doc if isinstance(doc, dict) else None


def write_attestation(commit, lenses, judge, tests, override_reason=""):
    """記下「這個 commit 被審查過」。

    刻意存在 `.fable/`（本閘自己 gitignore 的目錄）：它是**本機的證據**，
    不是要隨 repo 散佈的東西。綁的是 commit hash，所以改一行程式之後它就
    對不上了——這正是它要防的 TOCTOU。
    """
    # `.fable/` 是本 kit 的本機狀態目錄，而「只在自己建立時寫 `.gitignore`」的
    # 規則原本只在 goal_gate 那一份。這裡是**第三個**會建出該目錄的寫入者：
    # 先跑到的話，goal_gate 的 `fresh` 從此恆為 False，`.gitignore` 永遠不會寫，
    # 於是採用本 kit 的 repo 會把 attestation 與 goal_state.json（含跑過的測試
    # 指令）暴露給 `git add -A`。本 repo 因為根目錄 .gitignore 有 `.fable/` 而
    # 看不出來——那正是「只在自己身上驗過」的典型盲點。
    # 判準是「**這個目錄裡有沒有 `.gitignore`**」，與 goal_gate 的
    # `ensure_state_dir` 逐字相同。上面那段註解說對了風險，實作卻抄了
    # goal_gate 自己已經記載為錯誤的舊判準（「目錄是不是我建的」）——於是
    # repo 自己帶了 `.fable/`（committed .gitkeep、手動 mkdir）時，`fresh`
    # 恆為 False，`.gitignore` 永遠不會寫。實測在一個沒有任何 .gitignore 的
    # 拋棄式 repo 裡跑 --attest：`git status` 出現 `?? .fable/`，
    # attestation 與 goal_state.json 都進得了 `git add -A`（2026-09-06 抗辯）。
    fable_dir = os.path.dirname(ATTEST_DIR)
    fresh = not os.path.exists(os.path.join(fable_dir, ".gitignore"))
    os.makedirs(ATTEST_DIR, exist_ok=True)
    if fresh:
        with open(os.path.join(fable_dir, ".gitignore"), "w",
                  encoding="utf-8", newline="") as fh:
            fh.write("*" + chr(10))
    doc = {
        "reviewed_commit": commit,
        "reviewed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "lenses": lenses,
        "judge": judge,
        "tests": tests,
        "adversarial_review_bypassed": bool(override_reason),
        "bypass_reason": override_reason,
    }
    # 兩件事必須分開，混成一個旗標會把「留痕」變成「鎖死」：
    #   `adversarial_review_bypassed` ＝ **這一筆**是破窗收據，不是審查。
    #   `bypassed_earlier`            ＝ 這個 commit 曾經破窗過（永久痕跡）。
    #
    # 上一版兩者合一：破窗之後補跑三鏡頭再 `--attest`，仍被標成 bypassed，
    # 於是 `check_review` 永遠擋，而它的錯誤訊息叫人做的正是剛剛做過的那件事
    # ——唯一的出口變成再破窗一次，把一個**確實審過**的版本標成未審查。
    # 率是 0，但發生之後是永久的；而 RG17 當時還把這個行為斷言成預期。
    prev = read_attestation(commit)
    if prev and (prev.get("adversarial_review_bypassed")
                 or prev.get("bypassed_earlier")):
        doc["bypassed_earlier"] = True
        doc["earlier_bypass_reason"] = (prev.get("earlier_bypass_reason")
                                        or prev.get("bypass_reason") or "")
    with open(attestation_path(commit), "w", encoding="utf-8", newline="") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return doc


def parse_lenses(text):
    """`skeptic:REFUTED,red-team:REFUTED,simplifier:SURVIVED` → dict。

    三個鏡頭都必須有裁決。少一個就拒絕——「跑了兩個鏡頭」與「跑了三個」
    的差別，正是抗辯之所以是抗辯的原因。
    """
    got = {}
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError("鏡頭格式應為 `名稱:裁決`，收到：%r" % part)
        name, verdict = part.split(":", 1)
        got[name.strip()] = verdict.strip()
    missing = [n for n in LENS_NAMES if n not in got]
    if missing:
        raise ValueError("缺少鏡頭裁決：%s" % ", ".join(missing))
    empty = [n for n in LENS_NAMES if not got[n]]
    if empty:
        raise ValueError("鏡頭裁決不得留白：%s" % ", ".join(empty))
    return got


# ── 前置條件 ──────────────────────────────────────────────────────────────
def check_clean_tree():
    out = run(["git", "status", "--porcelain"])
    if out.returncode != 0:
        return "無法讀取 git 狀態"
    dirty = [l for l in (out.stdout or "").splitlines() if l.strip()]
    return "工作區不乾淨（%d 項未提交）" % len(dirty) if dirty else ""


def check_version_matches(version):
    try:
        with open(VERSION_FILE, encoding="utf-8") as fh:
            on_disk = fh.read().strip()
    except OSError:  # quiet-ok: 回傳的字串就是印給使用者看的前置條件失敗理由
        return "讀不到 VERSION"
    if on_disk != version:
        return "VERSION 是 %s，要發的是 %s" % (on_disk, version)
    try:
        with open(CHANGELOG, encoding="utf-8") as fh:
            body = fh.read()
    except OSError:  # quiet-ok: 同上，回傳的字串會被印出來並中止發佈
        return "讀不到 CHANGELOG.md"
    if not re.search(r"^## \[%s\]" % re.escape(version), body, re.M):
        return "CHANGELOG.md 沒有 [%s] 這一節" % version
    return ""


def check_tests():
    out = run([sys.executable, "-m", "pytest", "tests/", "-q"])
    tail = (out.stdout or "").strip().splitlines()
    summary = tail[-1] if tail else ""
    return ("" if out.returncode == 0 else "測試沒有全綠：%s" % summary), summary


def check_review(commit, override_reason):
    """審查證據必須存在，而且綁在**這個** commit 上。

    綁 commit 是這道檢查的全部意義：審查之後再改一行，attestation 的
    `reviewed_commit` 就與 HEAD 對不上，於是舊審查不能拿來發新內容。
    """
    if override_reason:
        return ""
    doc = read_attestation(commit)
    if doc is None:
        return ("這個 commit 沒有抗辯審查紀錄（%s）。\n"
                "  先跑三鏡頭抗辯，再用 --attest 記錄；真的緊急就用 "
                "--override-review --reason \"…\"（會留痕）。" % commit[:12])
    if doc.get("reviewed_commit") != commit:
        return ("審查紀錄綁的是 %s，HEAD 是 %s——審查之後程式又改過了。"
                % (str(doc.get("reviewed_commit"))[:12], commit[:12]))
    # 破窗的痕跡**不是**審查。這裡原本只看 `reviewed_commit`，於是一次
    # `--override-review` 留下的紀錄會在下一次不帶旗標的發佈被當成合格審查
    # 放行，而發佈說明也不再標 ADVERSARIAL_REVIEW_BYPASSED——留痕是這條通道
    # 獲准存在的唯一條件，而它把自己的痕跡洗掉了。兩個獨立鏡頭同時抓到。
    if doc.get("adversarial_review_bypassed"):
        return ("這個 commit 只有一筆**跳過審查**的紀錄（理由：%s），那不是審查。\n"
                "  要正式發佈就先跑三鏡頭抗辯再 --attest；仍要跳過就每次都明示 "
                "--override-review --reason \"…\"。"
                % (doc.get("bypass_reason") or "未填"))
    if not doc.get("judge"):
        return "審查紀錄沒有裁定（judge 留白）——形式齊全是最容易的假綠。"
    lenses = doc.get("lenses")
    if not isinstance(lenses, dict):
        return "審查紀錄的 lenses 不是一組鏡頭裁決：%r" % (lenses,)
    # 讀取端與寫入端必須是**同一份標準**。原本這裡只判「非空」，於是
    # `{"x": "y"}` 過得去——而 `parse_lenses`（寫入端）要求三個具名鏡頭且
    # 不得留白。把關不可逆動作的是鬆的那一側，等於嚴格那一側白做。
    missing = [n for n in LENS_NAMES if not str(lenses.get(n, "")).strip()]
    if missing:
        return ("審查紀錄缺這些鏡頭的裁決：%s（有的是 %s）"
                % (", ".join(missing), ", ".join(sorted(lenses)) or "無"))
    return ""


def preflight(version, override_reason):
    commit = head_commit()
    if not commit:
        return ["不在 git repo 裡，或 git 不可用"], "", ""
    problems = []
    for p in (check_clean_tree(), check_version_matches(version)):
        if p:
            problems.append(p)
    test_problem, summary = check_tests()
    if test_problem:
        problems.append(test_problem)
    p = check_review(commit, override_reason)
    if p:
        problems.append(p)
    # `gh` 在 do_release 的最後一步才用到，而它前面是 `git push`——不可逆。
    # 沒有這條，PATH 裡少一個 gh 就會變成「tag 推上去了、Release 沒建成」，
    # 而檔頭說這是一筆交易。前置條件要在不可逆動作之前問完。
    # 驗的是 `gh auth status` 不是 `gh --version`：後者只回答「PATH 上有沒有這個
    # 執行檔」。實測 `GH_TOKEN=invalid gh --version` rc=0 而 `gh auth status` rc=1
    # ——token 過期／scope 不足時，前置條件會放行，然後在**不可逆的 git push
    # 之後**才炸。這道閘的檔頭說前置條件要在不可逆動作之前問完。
    gh = run(["gh", "auth", "status"])
    if gh.returncode != 0:
        problems.append("`gh` 不可用或未通過認證（rc=%d）——它是建立 Release 的"
                        "唯一途徑，而它前面的 git push 不可逆。%s"
                        % (gh.returncode, (gh.stderr or gh.stdout or "").strip()[:200]))
    return problems, commit, summary


# ── 發佈 ──────────────────────────────────────────────────────────────────
def do_release(version, commit, override_reason):
    tag = "v%s" % version
    notes = "見 CHANGELOG.md 的 [%s] 一節。" % version
    if override_reason:
        notes += ("\n\n⚠ ADVERSARIAL_REVIEW_BYPASSED\n理由：%s\ncommit：%s"
                  % (override_reason, commit))
    else:
        # 事後補審查的版本仍要帶著它曾經破窗的痕跡——留痕是那條通道獲准存在的
        # 條件，而「後來補審了」不等於「沒有發生過」。這一行讓痕跡活下來，
        # 同時不再把一個確實審過的版本標成未審查。
        prev = read_attestation(commit)
        if prev and prev.get("bypassed_earlier"):
            notes += ("\n\nℹ️ 這個 commit 曾經以緊急出口發佈過一次（理由：%s），"
                      "之後補跑了完整的抗辯審查。"
                      % (prev.get("earlier_bypass_reason") or "未記錄"))
    out = run(["git", "tag", "-a", tag, "-m", "release %s" % version])
    if out.returncode != 0 and "already exists" not in (out.stderr or ""):
        return "建立 tag 失敗：%s" % (out.stderr or "").strip()
    # tag 指向的 commit 必須就是被審查的那一個，而且要在 **push 之前**驗。
    # 第一版把這段放在 push 後面，於是不一致時「指向未審查程式的公開 tag」
    # 已經推出去了——而最會踩到它的正是上面那條 `already exists` 分支：
    # 一個早就存在、指向別處的舊 tag 會直接走到這裡。
    out = run(["git", "rev-list", "-n", "1", tag])
    pointed = (out.stdout or "").strip()
    if pointed != commit:
        return "tag %s 指向 %s，但審查的是 %s" % (tag, pointed[:12], commit[:12])
    out = run(["git", "push", "origin", tag])
    if out.returncode != 0:
        return "推送 tag 失敗：%s" % (out.stderr or "").strip()
    out = run(["gh", "release", "create", tag, "--title", tag, "--notes", notes])
    if out.returncode != 0:
        # tag 已經公開了，而這是不可逆的。只說「建立 Release 失敗」會讓人以為
        # 什麼都沒發生——檔頭稱這是一筆交易，那就得說清楚交易停在哪一步。
        return ("建立 Release 失敗：%s\n"
                "  ⚠ tag %s **已經推上 origin**（那一步不可逆）。要收回請自己下\n"
                "     git push origin :refs/tags/%s && git tag -d %s"
                % ((out.stderr or "").strip(), tag, tag, tag))
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fable Harness 發佈交易")
    ap.add_argument("version", nargs="?", help="要發佈的版號，例如 1.5.0")
    ap.add_argument("--check", action="store_true", help="只跑前置條件")
    ap.add_argument("--attest", action="store_true", help="記錄抗辯審查結果")
    ap.add_argument("--lenses", default="", help="skeptic:…,red-team:…,simplifier:…")
    ap.add_argument("--judge", default="", help="主迴圈的裁決")
    ap.add_argument("--tests", default="", help="測試摘要行（供人閱讀，非判準）")
    ap.add_argument("--override-review", action="store_true",
                    help="緊急跳過審查檢查（必須同時給 --reason，會留痕）")
    ap.add_argument("--reason", default="", help="跳過審查的理由")
    args = ap.parse_args(argv)

    if args.attest:
        commit = head_commit()
        if not commit:
            print("⛔ 不在 git repo 裡")
            return 1
        try:
            lenses = parse_lenses(args.lenses)
        except ValueError as e:  # quiet-ok: 下一行就把理由印出來並回 1
            print("⛔ %s" % e)
            return 1
        if not args.judge:
            print("⛔ --judge 不得留白：三個鏡頭之後還要有一個裁決")
            return 1
        # 乾跑不得留下任何紀錄——這條在下面 `--check` 那裡寫過一次，卻只擋了
        # `--override-review` 那一半：`--check --attest` 照樣把一份真的審查記錄
        # 寫進 .fable/attestations/，於是「只是看看」就把該 commit 永久標成已審查
        # （2026-09-06 抗辯實測）。同一條不變式的兩個入口，只掃了一個。
        # 上面的格式檢查照跑，所以 `--check --attest` 仍是有用的乾跑：它會告訴你
        # 鏡頭字串與裁決寫對了沒，只是不落地。
        if args.check:
            print("✅ 乾跑：審查記錄格式正確，未寫入 %s" % attestation_path(commit))
            return 0
        # 不在這裡跑測試：`tests` 欄位沒有任何讀者（`check_review` 只讀
        # `reviewed_commit`），而跑一次全套要 20 秒——一次發佈會跑三次，
        # 其中這一次的結果直接被丟掉。要記就由使用者用 --tests 貼進來。
        doc = write_attestation(commit, lenses, args.judge, args.tests)
        print("✅ 已記錄審查：%s" % attestation_path(commit))
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        return 0

    # `.strip()`：`--reason " "` 通得過「沒有理由的跳過等於沒有紀錄」，實測
    # 完整發佈後落地的憑證是 `"bypass_reason": " "`。goal_gate 的
    # `block_unexplained_shelf` 早就修過一模一樣的事（註解逐字寫「原本讓一個
    # 空白字元就解除封鎖」），沒掃到這裡（2026-09-06 抗辯）。
    args.reason = args.reason.strip()
    if args.override_review and not args.reason:
        print("⛔ --override-review 必須同時給 --reason：沒有理由的跳過等於沒有紀錄")
        return 1
    override = args.reason if args.override_review else ""

    if not args.version:
        print("⛔ 要發佈就得給版號（或用 --attest / --check）")
        return 1

    problems, commit, summary = preflight(args.version, override)
    if problems:
        print("⛔ 發佈前置條件未通過：")
        for p in problems:
            print("  - %s" % p)
        return 1
    print("✅ 前置條件全過（%s，%s）" % (commit[:12], summary))
    if override:
        print("⚠ 本次跳過抗辯審查，理由：%s" % override)
    if args.check:
        return 0   # 乾跑不得留下任何紀錄：一次 `--check --override-review`
                   # 曾經就把該 commit 永久標成「已審查」，而使用者只是在看看

    if override:
        # 破窗要留痕，而且要留在**本機**：GitHub 的發佈說明是同一個人事後可以
        # 編輯的東西。寫在這裡而不是 preflight 之後，因為只有真的要發佈才算破窗。
        write_attestation(commit, {}, "", summary, override_reason=override)

    problem = do_release(args.version, commit, override)
    if problem:
        print("⛔ %s" % problem)
        return 1
    print("✅ 已發佈 v%s" % args.version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
