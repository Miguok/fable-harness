# -*- coding: utf-8 -*-
"""發佈交易（scripts/release.py）的驗收——未經抗辯的東西不得發出去。

驗收項目清單：
  RG1 沒有審查紀錄 → 擋（這是本檔存在的主因）
  RG2 RG1 的配對：有對得上的審查紀錄 → 前置條件通過（閘不得把正常流程鎖死）
  RG3 審查紀錄綁的是舊 commit → 擋（TOCTOU：審查後又改了程式）
  RG4 工作區不乾淨 → 擋
  RG5 VERSION 與要發的版號不符 → 擋
  RG6 CHANGELOG 沒有該版本章節 → 擋
  RG7 測試沒全綠 → 擋
  RG8 緊急出口：`--override-review` 沒給理由 → 擋（沒有理由等於沒有紀錄）
  RG9 RG8 的配對：給了理由 → 放行，且 attestation 標記已跳過
  RG10 三個鏡頭少一個 → --attest 拒絕記錄
  RG11 RG10 的配對：三個都給 → 記錄成功且欄位齊全
  RG12 接線：兩份維護文件都必須把發佈導向 scripts/release.py
  RG13 接線：腳本真的跑得起來（檔案存在 ≠ 跑得起來）
  RG25 推送：main 與驗過的 tag 物件一次 atomic 推上去（argv 逐字）；gh 帶 --verify-tag
  RG26 推送失敗 → 不建 Release，訊息帶原始診斷，不對遠端現況下保證
  RG28 本機 tag 讀不到／建不起來／前綴同名／指向別處 → 不推送
  RG29 不在 main 上 → 前置條件擋下；在 main 上 → 不擋
  RG30A 真 git：遠端同名 tag 衝突 → 整筆被拒，遠端 main 不動
  RG30B 真 git：main 與 annotated tag 都推上去、不帶出別的 tag；gh 失敗後重跑只補 Release
  RG30C 真 git：本機 tag 是 lightweight／巢狀／別名 → 不推送
  RG30E 真 git：本機有名字等於 commit OID 的分支 → 推的仍是審過的 commit
  RG30D 隔離箱的每道檢查（共 11 例，各違反一道）故意違反都會被**那一道**在執行前擋下
  RG31 經 main()：跳過審查首發後用同一組參數重跑能補完；不帶 override 重跑被擋

執行命令：
  cd <repo> && python -m pytest tests/test_release_gate.py -v

══════════════════════════════════════
驗收邊界說明 + 執行紀錄（2026-09-06 00:2x GMT+8）
══════════════════════════════════════
對應：外審 P1-03／P2-03（`reports/open_design_questions_review_20260905_chatgpt_reply_2026-09-05.md`）
與處置票 F-03／F-06（`reports/open_design_questions_disposition_20260905.md`）。

來由：協議 §2 早已規定「對外發佈前必須抗辯」，而 1.4.1 與 1.4.2 的 CHANGELOG
逐字記載該規則的作者在同一天跳過它**兩次**，兩次都是發佈後才補審查，而那些
審查真的找出缺陷。文字規則這一層已被證明不夠。

執行命令：python -m pytest tests/test_release_gate.py -q
最後執行：2026-11-15 23:22 → 62 passed ✅（全套 717 passed, 4 skipped in 160.88s）
第六輪（審實際程式碼）修正：Codex 指出裸 OID 當 push 來源會被同名 ref 蓋過——RG30E 先紅
  （遠端 main 變成未審查的 c2），來源改 `^{commit}`／`^{tag}` 後綠；RG30D 擴成 11 例，
  每例用 match 釘住擋下它的那一道檢查；推送失敗訊息補「守衛擋下」一條、刪掉可推出的
  「兩者都出現」，RG26 改用各條獨有的字樣。突變 17 個（新增「拿掉 ^{commit}」）全部被抓到。
2026-11-15 補「發佈沒有推 main」（RG25–RG31，無 RG27）：
  先紅：RG25 兩例紅（舊碼第一個呼叫是 `git tag -a`，沒有讀 tag、沒有推 main）；
    RG19 紅（舊訊息教人刪遠端 tag）；RG26 兩例紅；RG29 三例紅（沒有分支檢查）。
    RG20／RG20b／RG7b／RG16／RG24 在新流程下轉紅，原因是舊假 run 對所有指令回同一字串
    或沒回 symbolic-ref——已改用依序比對的 FakeGit，或替換 check_on_main。
  突變 16 個全部被抓到（跑完還原、位元組一致；第六輪後為 17 個）：拿掉 --atomic／main refspec／
    --no-follow-tags／--no-recurse-submodules／--verify-tag、tag refspec 改用名稱或 commit、
    拿掉 object／type＋object／名字檢查、refname 改前綴比對、忽略 tag -a 的 rc、
    HEAD 檢查改 startswith 或拿掉、推送失敗仍建 Release、整段輸出先 strip。
  真 git 實測值：遠端 tag 衝突時 stderr 為
    ` ! [rejected] <oid> -> v9.9.9 (already exists)`，遠端 main 停在 c0；
    push.recurseSubmodules=only＋--no-recurse-submodules 時 main 與 tag 都推上去；
    重跑時推送 rc 0、tag 物件 OID 不變、gh 共呼叫 2 次。
  ⚠ 「只拿掉 objecttype＝tag」是等價突變（lightweight 的 object 欄是空的，指向檢查本來就擋），不列。

（以下為 09-06 14:47 那批的紀錄）
最後執行：2026-09-06 14:47 → 30 passed ✅（全套 409 passed in 38.89s）
第七輪新增 RG22-RG24，逐條突變驗過：
  `.fable/.gitignore` 又用舊判準 → RG22 紅。本檔的 write_attestation 是第三個
    會建出 `.fable/` 的寫入者，它的註解說對了風險、實作卻抄了 goal_gate 自己
    已記載為錯誤的舊判準；本 repo 看不出來，因為根 .gitignore 已列 `.fable/`。
  憑證不驗是不是物件 → RG23 紅（`printf '[]'` 之後 `--check` 直接 traceback）。
  純空白理由又算理由 → RG24 紅。⚠ **RG24 的第一版是假綠**：它只斷言 rc==1，
    而那個 1 來自版號對不上，不是空白理由；而且沒 monkeypatch check_tests，
    在 pytest 裡又跑一次整套 pytest，突變那輪實測 300.73 秒（RG7／RG16 同坑）。
    現已改成先把其餘前置條件全部放行，並斷言訊息內容。

（以下為 09-06 13:40 那批的紀錄）
最後執行：2026-09-06 13:40 → 27 passed ✅（全套 352 passed in 33.62s）
本輪新增 RG21：`--check --attest` 也不得留痕。突變（把乾跑的早退拿掉）→ RG21 紅，
tmp 目錄裡真的出現一份 `adversarial_review_bypassed: false` 的正式審查記錄。
RG16 早就把「乾跑不留痕」寫成不變式，卻只擋了 `--override-review` 那一半
——同一條不變式的兩個入口只掃了一個。

（以下為 09-06 00:29 那批的紀錄）
最後執行：2026-09-06 00:29 → 17 passed ✅（全套 239 passed）

驗收邊界——本檔測前置條件的判定，以及 `git push` 的實際效果：RG30 用真 git 推到
測試自己建的暫存 bare repo（GIT_ALLOW_PROTOCOL=file，碰不到網路；隔離箱的檢查見
RG30D）。`gh release create` 仍不在測試裡驅動，一律換成假的。

✅ 已驗收（本檔涵蓋）
  RG1-RG11 → 每條「必須被擋下」都有配對的「必須仍然做得到」，
    因為一個「什麼都擋」的閘也會讓前者全綠而讓專案完全發不出東西
  RG12／RG13 → 接線：腳本在文件寫明的發佈路徑上，而且真的跑得起來
⏳ 待驗收（本檔未涵蓋）
  對 GitHub 的實際行為（atomic 支援、分支保護時的 `[remote rejected]` 字樣、
    `gh release create --verify-tag` 的 API 行為）：測試只推到本機 bare。
    解鎖條件＝下一次真實發佈時觀察 main 與 tag 一起出現在 origin，並確認
    `gh release list` 顯示該版為 Latest。
  git 以非英文語系輸出時，推送失敗訊息裡依字樣對照的指示會對不上：作者機器
    （PowerShell、未設 LANG）實測為英文。解鎖條件＝出現非英文環境的使用者。
  已知限制（第六輪記錄，未修）：
    ① refs/replace：for-each-ref 讀物件時套用替代物件、push 傳原始物件，刻意偽造的
      替代物件能讓驗證看到假 tag。需要先在本機動手腳，與 `--no-verify` 同屬本閘不防的
      範圍。解鎖條件＝威脅模型擴大到「本機被人動過」。
    ② gh 沒帶 --repo：環境有 GH_REPO 指向別的 repo 時 Release 會建到那裡（既有問題）。
      解鎖條件＝把 origin 的 push url 解析成 OWNER/REPO 傳給 gh，另案處理。
    ③ 既有本機 tag 的訊息不檢查：四欄對就原樣推出，訊息含私料時只靠作者本機的
      leak-guard 擋（它不進版控）。腳本自己建的 tag 訊息固定是 `release <ver>`。
  server 端驗證（GitHub workflow 檢查 reviewed_commit == tag SHA）：
    本 repo 目前沒有 `.github/workflows`（實查：`git ls-files .github` 無輸出）。
    外審建議加，但那是把信任邊界從本機移到 server 的另一項工程。
    解鎖條件＝決定要不要引入 CI，以及由誰持有 attestation 的真實來源。
"""
import json
import os
import pathlib
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE = os.path.join(ROOT, "scripts", "release.py")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import release as rel  # noqa: E402


def _run(*args, cwd=None):
    return subprocess.run([sys.executable, RELEASE] + list(args),
                          capture_output=True, encoding="utf-8",
                          errors="replace", cwd=cwd or ROOT, timeout=300)


# ── 鏡頭裁決的解析（不碰檔案系統，快）──────────────────────────────────
def test_rg10_a_missing_lens_is_refused():
    """RG10：三個鏡頭少一個就不得記錄。

    「跑了兩個鏡頭」與「跑了三個」的差別，正是抗辯之所以是抗辯的原因：
    三鏡頭過半存活才採信，兩個鏡頭湊不出過半這個概念。
    """
    with pytest.raises(ValueError, match="simplifier"):
        rel.parse_lenses("skeptic:REFUTED,red-team:REFUTED")


def test_rg11_all_three_lenses_parse():
    """RG11：RG10 的配對——三個都給就要收得下，否則這道閘會把正常流程鎖死。"""
    got = rel.parse_lenses("skeptic:REFUTED, red-team:REFUTED, simplifier:SURVIVED")
    assert got == {"skeptic": "REFUTED", "red-team": "REFUTED",
                   "simplifier": "SURVIVED"}


def test_rg10b_a_blank_verdict_is_refused():
    """RG10b：鏡頭名字在、裁決留白，等於沒跑——形式齊全是最容易的假綠。"""
    with pytest.raises(ValueError, match="不得留白"):
        rel.parse_lenses("skeptic:REFUTED,red-team:,simplifier:SURVIVED")


# ── 審查證據綁 commit（TOCTOU）──────────────────────────────────────────
def test_rg1_no_attestation_blocks(tmp_path, monkeypatch):
    """RG1：這個 commit 沒有審查紀錄 → 擋。本檔存在的主因。"""
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    assert rel.check_review("a" * 40, "")


def test_rg2_a_matching_attestation_passes(tmp_path, monkeypatch):
    """RG2：RG1 的配對——審查紀錄對得上就必須放行。

    沒有這一條，一個「永遠擋」的閘也會讓 RG1 綠，而那會讓專案完全發不出
    任何東西——比沒有這道閘更糟。
    """
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    commit = "b" * 40
    rel.write_attestation(commit, {"skeptic": "REFUTED", "red-team": "REFUTED",
                                   "simplifier": "REFUTED"}, "ship", "9 passed")
    assert rel.check_review(commit, "") == ""


def test_rg3_an_attestation_for_another_commit_blocks(tmp_path, monkeypatch):
    """RG3：審查之後又改了程式 → 舊審查不得拿來發新內容。

    這是 TOCTOU：只要求「存在一份審查」的話，審查完再改一行就能繞過整道閘，
    而那一行正是沒有人看過的那一行。
    """
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    reviewed, head = "c" * 40, "d" * 40
    rel.write_attestation(reviewed, {"skeptic": "REFUTED"}, "ship", "9 passed")
    # 檔名是 HEAD，內容綁的卻是別的 commit：手動偽造這一步，因為真實情況
    # （改了程式、commit 變了）在測試裡等價於「檔案在、內容對不上」。
    os.replace(os.path.join(str(tmp_path), reviewed + ".json"),
               os.path.join(str(tmp_path), head + ".json"))
    problem = rel.check_review(head, "")
    assert problem and "又改過了" in problem


def test_rg8_override_without_a_reason_blocks():
    """RG8：緊急出口沒給理由 → 擋。

    沒有理由的跳過等於沒有紀錄，而留痕正是這條出口存在的唯一條件。
    """
    out = _run("1.0.0", "--override-review")
    assert out.returncode == 1
    assert "必須同時給 --reason" in out.stdout


def test_rg9_override_with_a_reason_skips_the_review_check(tmp_path, monkeypatch):
    """RG9：RG8 的配對——給了理由就要放行，而且紀錄要標明「已跳過」。

    保留緊急出口的理由：沒有它，真正緊急的人會發明更髒的旁路，而那些旁路
    不會留下任何紀錄。有記錄的破窗比沒記錄的翻牆好。
    """
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    assert rel.check_review("e" * 40, "critical security rollback") == ""
    doc = rel.write_attestation("e" * 40, {}, "", "", "critical security rollback")
    assert doc["adversarial_review_bypassed"] is True
    assert doc["bypass_reason"] == "critical security rollback"


# ── 其餘前置條件 ──────────────────────────────────────────────────────────
def test_rg5_a_version_mismatch_blocks():
    """RG5：VERSION 與要發的版號不符 → 擋（打錯版號是最容易犯的一種）。"""
    problem = rel.check_version_matches("0.0.0-nope")
    assert problem and "VERSION" in problem


def test_rg6_a_missing_changelog_section_blocks(tmp_path, monkeypatch):
    """RG6：CHANGELOG 沒有該版章節 → 擋。

    發一個沒有人寫過說明的版本，等於把「這版改了什麼」留給讀 commit 的人拼。
    """
    v = tmp_path / "VERSION"
    v.write_text("9.9.9\n", encoding="utf-8", newline="")
    c = tmp_path / "CHANGELOG.md"
    c.write_text("# Changelog\n\n## [9.9.8] — x\n", encoding="utf-8", newline="")
    monkeypatch.setattr(rel, "VERSION_FILE", str(v))
    monkeypatch.setattr(rel, "CHANGELOG", str(c))
    problem = rel.check_version_matches("9.9.9")
    assert problem and "CHANGELOG" in problem


def test_rg6b_a_present_changelog_section_passes(tmp_path, monkeypatch):
    """RG6b：RG5／RG6 的配對——版號與章節都對就必須放行。"""
    v = tmp_path / "VERSION"
    v.write_text("9.9.9\n", encoding="utf-8", newline="")
    c = tmp_path / "CHANGELOG.md"
    c.write_text("# Changelog\n\n## [9.9.9] — x\n", encoding="utf-8", newline="")
    monkeypatch.setattr(rel, "VERSION_FILE", str(v))
    monkeypatch.setattr(rel, "CHANGELOG", str(c))
    assert rel.check_version_matches("9.9.9") == ""


def test_rg4_a_dirty_tree_blocks(monkeypatch):
    """RG4：工作區不乾淨 → 擋。

    未提交的改動不會進 tag，於是發出去的內容與作者眼前看到的不是同一份——
    而作者是照眼前那份下「可以發了」這個判斷的。

    ⚠ 第一版在 tmp_path 開了個髒 repo，然後斷言 `git status --porcelain` 有
    輸出——`check_clean_tree()` **一次都沒被呼叫**（`run()` 寫死 `cwd=ROOT`，
    指不到 tmp_path）。它斷言的是「git 會回報髒檔」，不是「這道閘會擋」，
    把整個函式刪掉它照樣綠。斷言對象必須是被保護的那個東西。
    """
    monkeypatch.setattr(rel, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=" M x.txt\n?? y.txt\n", stderr=""))
    problem = rel.check_clean_tree()
    assert "不乾淨" in problem and "2" in problem, f"髒工作區沒被擋：{problem!r}"


def test_rg4b_a_clean_tree_passes(monkeypatch):
    """RG4b：RG4 的配對——乾淨的工作區必須放行。"""
    monkeypatch.setattr(rel, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout="", stderr=""))
    assert rel.check_clean_tree() == ""


def test_rg7_a_red_suite_blocks_release(monkeypatch):
    """RG7：測試沒全綠 → 擋，而且理由要帶著摘要行。

    只說「測試失敗」而不說哪一行，會讓人跑去重跑一次才知道發生什麼事。

    ⚠ 這裡把 `check_tests` 換掉，**不真的跑一次全套**：第一版直接呼叫它，
    於是 pytest 在 pytest 裡再跑一次整個 suite——實測 300 秒還沒跑完
    （2026-09-06）。一條讓每次驗證多花五分鐘的測試，下一步一定是被跳過，
    而被跳過的測試等於沒有。這裡驗的是 preflight **怎麼處理**紅燈回報，
    那才是這條的斷言對象；`check_tests` 本身只是一次 subprocess 呼叫。
    """
    monkeypatch.setattr(rel, "check_tests",
                        lambda: ("測試沒有全綠：1 failed, 8 passed", "1 failed, 8 passed"))
    monkeypatch.setattr(rel, "check_clean_tree", lambda: "")
    monkeypatch.setattr(rel, "check_on_main", lambda: "")   # RG29 另測
    monkeypatch.setattr(rel, "check_version_matches", lambda v: "")
    monkeypatch.setattr(rel, "check_review", lambda c, o: "")
    # `head_commit` 與 `gh auth status` 也換掉：preflight 的**前段**原本是真的在
    # 跑，於是這條的斷言取決於「當下的 cwd 是不是一個 git repo」「gh 有沒有登入」。
    # 實測把工作樹複製到別的路徑（不含 .git）後 RG7／RG7b 雙雙失敗——preflight
    # 第一行就 return，`check_tests` 從來沒被呼叫。斷言掛在程式沒走到的那一格，
    # 是本專案反覆出現的假綠形態（2026-09-06 抗辯，RG24 同批修過一次）。
    monkeypatch.setattr(rel, "head_commit", lambda: "a" * 40)
    monkeypatch.setattr(rel, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout="", stderr=""))
    problems, _, summary = rel.preflight("9.9.9", "")
    assert any("測試沒有全綠" in p for p in problems), "紅燈沒有擋下發佈"
    assert "1 failed" in summary, "擋下的理由沒有帶著摘要行"


def test_rg7b_a_green_suite_does_not_block(monkeypatch):
    """RG7b：RG7 的配對——全綠時前置條件必須通過。

    沒有這條，一個「永遠回報有問題」的 preflight 也會讓 RG7 綠。
    """
    monkeypatch.setattr(rel, "check_tests", lambda: ("", "222 passed in 19.77s"))
    monkeypatch.setattr(rel, "check_clean_tree", lambda: "")
    monkeypatch.setattr(rel, "check_on_main", lambda: "")   # RG29 另測
    monkeypatch.setattr(rel, "check_version_matches", lambda v: "")
    monkeypatch.setattr(rel, "check_review", lambda c, o: "")
    monkeypatch.setattr(rel, "head_commit", lambda: "a" * 40)   # 見 RG7 的說明
    monkeypatch.setattr(rel, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout="", stderr=""))
    problems, commit, summary = rel.preflight("9.9.9", "")
    assert problems == [], f"全綠卻被擋：{problems}"
    assert commit and "passed" in summary


# ── 接線：這支腳本必須在文件寫明的發佈路徑上 ────────────────────────────
@pytest.mark.parametrize("doc", ["MAINTAINING.md", "MAINTAINING.zh-TW.md"])
def test_rg12_the_documented_release_path_goes_through_this_script(doc):
    """RG12：兩份維護文件都必須把發佈導向 `scripts/release.py`。

    這是本套件自己的接線規則：一個「被呼叫才有用」的東西，交付時要同批附一條
    斷言**它在執行路徑上**的守衛。發佈腳本寫得再好，只要文件還教人手動下
    `gh release create`，它就永遠不會被執行——那比沒寫更糟，因為它會被當成
    「已交付」而從待辦清單上劃掉。

    斷言對象是**文件實際的內容**，不是我記得寫過什麼。
    """
    with open(os.path.join(ROOT, doc), encoding="utf-8") as fh:
        body = fh.read()
    assert "scripts/release.py" in body, (
        f"{doc} 沒有把發佈導向 scripts/release.py——腳本不在任何執行路徑上"
    )


def test_rg13_release_script_is_reachable_and_self_describing():
    """RG13：腳本要真的跑得起來，而且 `--help` 講得出自己是什麼。

    「檔案存在」不等於「跑得起來」——1.4.x 有過一支因為缺 BOM 從第一天就
    跑不動的腳本，而它被記為已交付。這條驅動真實的行程。
    """
    out = _run("--help")
    assert out.returncode == 0, f"腳本跑不起來：{out.stderr[:300]}"
    assert "--override-review" in out.stdout
    assert "--attest" in out.stdout


def test_rg14_a_bypass_record_is_not_accepted_as_a_review(tmp_path, monkeypatch):
    """RG14：破窗的痕跡**不是**審查——它不得讓下一次發佈免審。

    2026-09-06 第二輪抗辯的 P0，兩個獨立鏡頭同時抓到：`check_review` 原本只看
    `reviewed_commit`，於是一次 `--override-review` 留下的紀錄會在下一次**不帶
    任何旗標**的發佈被當成合格審查放行，而發佈說明也不再標
    `ADVERSARIAL_REVIEW_BYPASSED`。留痕是這條通道獲准存在的唯一條件，而它
    把自己的痕跡洗掉了。

    RG9 只斷言「痕跡有被寫下」，沒有斷言「痕跡會被讀」——這正是那一對裡
    缺掉的另一半。
    """
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    commit = "f" * 40
    rel.write_attestation(commit, {}, "", "", override_reason="prod outage")

    problem = rel.check_review(commit, "")
    assert problem, "跳過審查的紀錄被當成一次完成的抗辯審查"
    assert "不是審查" in problem


def test_rg15_an_empty_lens_record_is_not_accepted(tmp_path, monkeypatch):
    """RG15：鏡頭裁決或裁定留白的紀錄不算審查——形式齊全是最容易的假綠。"""
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    commit = "0" * 40
    rel.write_attestation(commit, {}, "", "9 passed")
    assert rel.check_review(commit, ""), "空的鏡頭裁決被當成審查"

    # 只有一個鏡頭仍然不算：讀取端與寫入端必須是**同一份標準**。原本這裡只判
    # 「lenses 非空」，於是 `{"x": "y"}` 過得去——而把關不可逆動作的正是這一側，
    # `parse_lenses`（寫入端）的嚴格因此白做（2026-09-06 抗辯）。
    rel.write_attestation(commit, {"skeptic": "REFUTED"}, "ship", "9 passed")
    problem = rel.check_review(commit, "")
    assert problem and "red-team" in problem, f"只有一個鏡頭卻放行：{problem!r}"

    rel.write_attestation(commit, {"x": "y"}, "ok", "9 passed")
    assert rel.check_review(commit, ""), "亂取名的鏡頭被當成審查"

    rel.write_attestation(commit, {"skeptic": "REFUTED", "red-team": "REFUTED",
                                   "simplifier": "REFUTED"}, "ship", "9 passed")
    assert rel.check_review(commit, "") == "", "齊全的紀錄反而被擋——閘不得鎖死正常流程"


def test_rg16_a_dry_run_leaves_no_record(tmp_path, monkeypatch):
    """RG16：`--check` 是乾跑，不得留下任何紀錄。

    第二輪抗辯實測：`--check --override-review --reason "just looking"` 會把該
    commit **永久**標成已審查，而使用者只是在看看。乾跑留下持久後果，是這道閘
    最不該有的行為。

    ⚠ 這裡 in-process 呼叫 `main`，不起子行程：`--check` 會跑一次全套測試，
    而在 pytest 裡起子行程跑 pytest 就是無限遞迴（同一個坑第二次，見 RG7）。
    """
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    monkeypatch.setattr(rel, "check_tests", lambda: ("", "222 passed"))
    monkeypatch.setattr(rel, "check_clean_tree", lambda: "")
    monkeypatch.setattr(rel, "check_on_main", lambda: "")   # RG29 另測
    monkeypatch.setattr(rel, "check_version_matches", lambda v: "")
    monkeypatch.setattr(rel, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout="gh version 2.90.0\n", stderr=""))

    rc = rel.main(["9.9.9", "--check", "--override-review", "--reason", "just looking"])
    assert rc == 0, "前置條件被 monkeypatch 成全過，乾跑卻沒通過"
    assert not list(tmp_path.iterdir()), (
        f"乾跑留下了紀錄：{[p.name for p in tmp_path.iterdir()]}"
    )


def test_rg17_a_later_attest_keeps_the_trace_without_locking_the_release(
        tmp_path, monkeypatch):
    """RG17：事後補審查要**留住痕跡**，但不得把發佈鎖死。

    這條測試上一版斷言的是缺陷本身（`adversarial_review_bypassed is True`），
    於是把它鎖進了規格：破窗之後補跑三鏡頭再 `--attest`，紀錄仍被標成破窗，
    `check_review` 永遠擋，而它的錯誤訊息叫人做的**正是剛剛做過的那件事**。
    唯一的出口是再破窗一次，把一個確實審過的版本標成未審查。

    根因是兩件事被混成一個旗標。分開之後：
      `adversarial_review_bypassed` ＝ **這一筆**是破窗收據，不是審查
      `bypassed_earlier`            ＝ 這個 commit 曾經破窗過（永久痕跡）

    率是 0——要先破窗一次才會遇到。但性質是閂鎖：發生之後永久。而測試把缺陷
    寫成預期行為，比缺陷本身更難清，因為它會讓正確的修法變成「破壞測試」。
    """
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    commit = "a" * 40
    rel.write_attestation(commit, {}, "", "", override_reason="prod outage")
    assert rel.check_review(commit, ""), "前置不成立：破窗紀錄本來就該擋"

    doc = rel.write_attestation(
        commit, {"skeptic": "REFUTED", "red-team": "REFUTED",
                 "simplifier": "REFUTED"}, "ship", "9 passed")

    assert doc["bypassed_earlier"] is True, "破窗的痕跡被事後的審查抹掉了"
    assert doc["earlier_bypass_reason"] == "prod outage", "跳過的理由不見了"
    assert doc["adversarial_review_bypassed"] is False, (
        "補跑了完整審查，紀錄卻仍被標成破窗——發佈從此鎖死"
    )
    assert rel.check_review(commit, "") == "", (
        "補跑了完整審查仍然發不出去；錯誤訊息叫人做的正是剛剛做過的事"
    )


def test_rg20_the_earlier_bypass_is_still_announced_in_the_release_notes(
        tmp_path, monkeypatch):
    """RG20：RG17 的配對——痕跡留住了，就必須**被看見**。

    只有 RG17 的話，一個「把 `bypassed_earlier` 寫進檔案然後從不讀它」的實作
    也會通過，而那等於沒有留痕：留痕的意義是下游讀得到。
    """
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    commit = "b" * 40
    rel.write_attestation(commit, {}, "", "", override_reason="prod outage")
    rel.write_attestation(commit, {"skeptic": "REFUTED", "red-team": "REFUTED",
                                   "simplifier": "REFUTED"}, "ship", "9 passed")

    notes = _release_notes(monkeypatch, commit)
    assert "曾經以緊急出口發佈過" in notes, f"發佈說明沒有帶出曾經破窗的痕跡：{notes!r}"
    assert "prod outage" in notes, "理由沒有帶出來"


def test_rg20b_an_ordinary_release_says_nothing_about_a_bypass(
        tmp_path, monkeypatch):
    """RG20b：從沒破窗過的版本，發佈說明不得無中生有地提到破窗。"""
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    commit = "c" * 40
    rel.write_attestation(commit, {"skeptic": "REFUTED", "red-team": "REFUTED",
                                   "simplifier": "REFUTED"}, "ship", "9 passed")
    notes = _release_notes(monkeypatch, commit)
    assert "緊急出口" not in notes, notes


def _release_notes(monkeypatch, commit):
    """跑一次成功的 do_release（本機已有正確的 tag），回傳交給 gh 的發佈說明。"""
    push = PUSH[:-2] + [commit + "^{commit}:refs/heads/main", TAG_OID + "^{tag}:refs/tags/v9.9.9"]
    fake = FakeGit([(READ, 0, _tag_line(target=commit), ""), (push, 0, "", ""),
                    (GH, 0, "", "")])
    monkeypatch.setattr(rel, "run", fake)
    assert rel.do_release("9.9.9", commit, "") == ""
    fake.done()
    gh = fake.calls[-1]
    return gh[gh.index("--notes") + 1]

def test_rg18_preflight_checks_that_gh_is_usable_not_merely_installed(monkeypatch):
    """RG18：`gh` 要驗**用得了**，不是驗 PATH 上有沒有這個執行檔。

    實測 `GH_TOKEN=invalid gh --version` rc=0 而 `gh auth status` rc=1——token
    過期或 scope 不足時，前置條件會放行，然後在**不可逆的 git push 之後**才炸。
    這道閘的檔頭寫著「前置條件要在不可逆動作之前問完」，那就得問對問題。
    """
    calls = []

    def fake_run(args, **kw):
        calls.append(list(args))
        rc = 1 if args[:3] == ["gh", "auth", "status"] else 0
        return SimpleNamespace(returncode=rc, stdout="", stderr="not logged in")

    monkeypatch.setattr(rel, "run", fake_run)
    monkeypatch.setattr(rel, "check_tests", lambda: ("", "9 passed"))
    monkeypatch.setattr(rel, "check_clean_tree", lambda: "")
    monkeypatch.setattr(rel, "check_version_matches", lambda v: "")
    monkeypatch.setattr(rel, "check_review", lambda c, o: "")
    monkeypatch.setattr(rel, "head_commit", lambda: "b" * 40)

    problems, _, _ = rel.preflight("9.9.9", "")
    assert any("gh" in p for p in problems), f"gh 認證失敗卻放行：{problems}"
    assert ["gh", "auth", "status"] in calls, "問的不是 `gh auth status`"


def test_rg19_a_failed_release_says_main_and_the_tag_are_already_public(monkeypatch):
    """RG19：push 成功、建立 Release 失敗時，必須講明 main 與 tag 已經公開。

    只說「建立 Release 失敗」會讓人以為什麼都沒發生。push 是不可逆的，而
    檔頭稱這是一筆交易——那就得說清楚交易停在哪一步，以及下一步做什麼。

    2026-11-15 改：舊版教人「刪遠端 tag 收回」——main 也推上去之後，刪 tag
    收不回已公開的 main，那個建議會讓人以為整筆發佈已撤回。現在改成先查
    Release 是不是其實已經建好（gh 可能成功了才逾時），再決定重跑還是停。
    """
    fake = FakeGit([(READ, 0, _tag_line(), ""), (PUSH, 0, "", ""),
                    (GH, 1, "", "HTTP 403: Resource not accessible")])
    monkeypatch.setattr(rel, "run", fake)
    problem = rel.do_release("9.9.9", COMMIT, "")
    fake.done()
    assert "main 與 tag 已推上 origin" in problem, f"沒告知已公開：{problem!r}"
    assert "rc=1" in problem and "HTTP 403: Resource not accessible" in problem, (
        "gh 的失敗原因沒帶出來：" + problem)
    assert "gh release view v9.9.9" in problem, "沒叫人先查 Release 是否其實已建"
    assert "不要重跑" in problem, "查到已存在時沒說停"
    assert "同一組參數" in problem, "沒說怎麼重跑"
    assert ":refs/tags/" not in problem, "仍在教人刪遠端 tag——收不回已公開的 main"


def test_rg21_a_dry_run_attest_writes_nothing(tmp_path, monkeypatch):
    """RG21：`--check --attest` 是乾跑，同樣不得留下紀錄。

    RG16 已經把「乾跑不留痕」寫成不變式，但它只擋了 `--override-review`
    那一半：`--attest` 分支在 `--check` 之前就 return，於是
    `--check --attest` 照樣把一份**真的**審查記錄寫進 `.fable/attestations/`，
    把該 commit 永久標成已審查（2026-09-06 抗辯實測）。同一條不變式的兩個
    入口，只掃了一個——正是本專案一再犯的「同類沒掃完」。

    配對是後半段：格式檢查照跑、錯誤照擋，否則乾跑就變成什麼都不做的空殼。
    """
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    monkeypatch.setattr(rel, "head_commit", lambda: "c" * 40)

    rc = rel.main(["--check", "--attest",
                   "--lenses", "skeptic:ok,red-team:ok,simplifier:ok",
                   "--judge", "看看而已"])
    assert rc == 0, "乾跑的格式是對的，卻沒通過"
    assert not list(tmp_path.iterdir()), (
        f"乾跑留下了審查記錄：{[p.name for p in tmp_path.iterdir()]}")

    bad = rel.main(["--check", "--attest", "--lenses", "skeptic:ok", "--judge", "x"])
    assert bad == 1, "乾跑不檢查鏡頭是否齊全，那它什麼都沒驗到"
    assert not list(tmp_path.iterdir()), "失敗的乾跑也不得留痕"


def test_rg22_the_state_dir_gets_a_gitignore_even_when_it_already_exists(tmp_path):
    """RG22：`.fable/` 早就存在時，`.gitignore` 仍然要寫。

    `write_attestation` 是**第三個**會建出 `.fable/` 的寫入者，它自己的註解
    逐字說明了風險，實作卻抄了 `goal_gate` 已經記載為錯誤的舊判準（「目錄是不是
    我建的」）。於是 repo 自己帶了 `.fable/`（committed `.gitkeep`、手動 mkdir）
    時 `.gitignore` 永遠不會寫，attestation 與 `goal_state.json`（裡面有跑過的
    測試指令）就進得了 `git add -A`。

    本 repo 看不出來，因為根目錄的 `.gitignore` 已經列了 `.fable/`——那正是
    「只在自己身上驗過」的盲點，兩個獨立鏡頭都指出這一條。
    """
    attest = tmp_path / ".fable" / "attestations"
    (tmp_path / ".fable").mkdir()          # 目錄先存在，但沒有 .gitignore
    monkey = str(attest)
    old = rel.ATTEST_DIR
    rel.ATTEST_DIR = monkey
    try:
        rel.write_attestation("a" * 40, {"skeptic": "ok"}, "judged", "9 passed")
    finally:
        rel.ATTEST_DIR = old
    gi = tmp_path / ".fable" / ".gitignore"
    assert gi.exists(), "`.fable/` 早就存在時 .gitignore 沒有補上"
    assert gi.read_text(encoding="utf-8").strip() == "*"


def test_rg23_a_valid_json_non_object_attestation_does_not_crash(tmp_path, monkeypatch):
    """RG23：合法 JSON 但不是物件的憑證不得讓發佈閘 traceback。

    實測 `printf '[]' > .fable/attestations/<HEAD>.json` 之後 `--check` 直接
    `AttributeError: 'list' object has no attribute 'get'`。方向是 fail-closed
    （發佈中止），但 `goal_gate.load_state` 早就對同一件事驗了
    `isinstance(s, dict)`，而這道閘的文案同樣叫人手動編 `.fable/`
    ——同一類沒掃到第二個寫入者。

    配對是最後一行：合法的物件仍要讀得回來，否則一個「一律回 None」的版本
    也會通過。
    """
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    commit = "b" * 40
    for junk in ("[]", '"x"', "null", "3"):
        (tmp_path / ("%s.json" % commit)).write_text(junk, encoding="utf-8")
        assert rel.read_attestation(commit) is None, junk
        assert "沒有抗辯審查紀錄" in rel.check_review(commit, ""), junk

    rel.write_attestation(commit, {"skeptic": "a", "red-team": "b",
                                   "simplifier": "c"}, "judged", "9 passed")
    assert isinstance(rel.read_attestation(commit), dict)
    assert rel.check_review(commit, "") == ""


def test_rg24_a_whitespace_only_reason_is_not_a_reason(tmp_path, monkeypatch, capsys):
    """RG24：`--reason " "` 不算理由。

    實測完整發佈流程（gh／push／pytest 以假物件替換）：`--reason " "` 一路
    通過，落地的憑證是 `"bypass_reason": " "`。`goal_gate` 的
    `block_unexplained_shelf` 早就修過一模一樣的事，註解逐字寫著「原本讓一個
    空白字元就解除封鎖」——沒掃到這裡（2026-09-06 抗辯）。

    ⚠ **這條測試的第一版是假綠**，兩個毛病一起犯：
      ① 它只斷言 `rc == 1`，而那個 1 來自**版號對不上**（VERSION 是 1.5.0，
         測試傳 9.9.9），不是來自空白理由。把 `.strip()` 拿掉，它照樣綠。
      ② 沒有 monkeypatch 掉 `check_tests`，於是它在 pytest 裡再跑一次整套
         pytest——突變測試那一輪實測 300.73 秒（RG7／RG16 踩過的同一個坑）。
    現在其餘前置條件全部先 monkeypatch 成通過，唯一能讓它失敗的就是理由本身，
    並且斷言訊息內容，而不是只看回傳碼。
    """
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    monkeypatch.setattr(rel, "check_tests", lambda: ("", "9 passed"))
    monkeypatch.setattr(rel, "check_clean_tree", lambda: "")
    monkeypatch.setattr(rel, "check_on_main", lambda: "")   # RG29 另測
    monkeypatch.setattr(rel, "check_version_matches", lambda v: "")
    monkeypatch.setattr(rel, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout="gh version 2.90.0\n", stderr=""))

    rc = rel.main(["9.9.9", "--check", "--override-review", "--reason", "   "])
    out = capsys.readouterr().out
    assert rc == 1, "純空白的理由被當成理由"
    assert "必須同時給 --reason" in out, (
        "擋是擋了，但不是因為理由空白——那代表這條測試斷言在別的原因上：" + out)
    assert not list(tmp_path.iterdir()), "失敗的乾跑留下了紀錄"

    # 配對：真的有理由時仍要放行，否則一個「永遠擋」的版本也會讓上面全綠。
    assert rel.main(["9.9.9", "--check", "--override-review",
                     "--reason", "hotfix for a live outage"]) == 0


# ── 推送：main 與 tag 一次 atomic 推上去（2026-11-15）─────────────────────
# 缺陷：do_release 原本只推 tag，不推 main。只跑腳本時公開 repo 會有新版的 tag
# 與 Release 頁，main 卻停在舊版，`git pull` 的使用者拿到舊程式。
COMMIT = "a1" * 20
TAG_OID = "7a" * 20          # 刻意與 COMMIT 不同：推的必須是 tag 物件，不是 commit
OTHER = "b2" * 20
FMT = ("--format=%(refname)%09%(objectname)%09%(objecttype)%09%(object)"
       "%09%(type)%09%(tag)")
READ = ["git", "for-each-ref", FMT, "refs/tags/v9.9.9"]
MAKE_TAG = ["git", "tag", "-a", "v9.9.9", "-m", "release 9.9.9", COMMIT]
PUSH = ["git", "push", "--atomic", "--no-follow-tags", "--no-recurse-submodules",
        "origin", COMMIT + "^{commit}:refs/heads/main", TAG_OID + "^{tag}:refs/tags/v9.9.9"]
GH = ["gh", "release", "create", "v9.9.9"]


def _tag_line(oid=TAG_OID, objtype="tag", target=COMMIT, ttype="commit",
              name="v9.9.9", ref="refs/tags/v9.9.9"):
    return "\t".join([ref, oid, objtype, target, ttype, name]) + "\n"


class FakeGit:
    """依序比對的假 run：每個案例給一份允許的呼叫序列。

    多出的呼叫、順序不對都當場 raise；`done()` 斷言序列用完（少了呼叫也抓得到）。
    git 指令逐字比對；gh 只比前綴（`--notes` 的內容由各測試自己看）。
    """

    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = []

    def __call__(self, args, **kw):
        args = list(args)
        self.calls.append(args)
        assert self.steps, "多出的呼叫：%r" % (args,)
        expect, rc, out, err = self.steps.pop(0)
        got = args[:len(expect)] if expect[0] == "gh" else args
        assert got == expect, "呼叫不符：\n  預期 %r\n  實得 %r" % (expect, args)
        return SimpleNamespace(returncode=rc, stdout=out, stderr=err)

    def done(self):
        assert not self.steps, "少了呼叫：%r" % (self.steps,)


@pytest.mark.parametrize("tag_exists", [False, True], ids=["new-tag", "tag-exists"])
def test_rg25_release_pushes_main_and_the_tag_object_in_one_atomic_push(
        monkeypatch, tag_exists):
    """RG25：main 與 tag 必須一次 atomic 推上去，推的是驗過的 tag 物件。

    argv 逐字比對，盯住的是這些各自有實測失效的旗標：
      `--atomic`               不加時遠端 tag 衝突會留下「main 已推、tag 被拒」的半套
      `--no-follow-tags`       使用者設了 push.followTags 時會把其他 tag 一起帶出去
      `--no-recurse-submodules` push.recurseSubmodules=only 會不推主 repo 卻回 rc 0
      `<TAG_OID>^{tag}:refs/tags/…` 推驗過的物件，不是名稱；`^{…}` 讓同名 ref 蓋不過它（RG30E）
    """
    steps = [] if tag_exists else [(READ, 0, "", ""), (MAKE_TAG, 0, "", "")]
    steps += [(READ, 0, _tag_line(), ""), (PUSH, 0, "", ""), (GH, 0, "", "")]
    fake = FakeGit(steps)
    monkeypatch.setattr(rel, "run", fake)
    assert rel.do_release("9.9.9", COMMIT, "") == ""
    fake.done()
    assert "--verify-tag" in fake.calls[-1], "gh 沒帶 --verify-tag：缺 tag 時會自己建一個"


@pytest.mark.parametrize("rc,stderr", [
    (1, " ! [rejected]        %s -> v9.9.9 (already exists)\n"
        "error: failed to push some refs to 'origin'" % TAG_OID),
    (127, "TimeoutExpired: Command timed out after 300 seconds"),
], ids=["rejected", "timeout-127"])
def test_rg26_a_failed_push_stops_and_does_not_claim_what_the_remote_holds(
        monkeypatch, rc, stderr):
    """RG26：推送失敗 → 不建 Release，訊息帶原始診斷，不判定遠端現況。

    rc 127 是 run() 把逾時／找不到執行檔轉出來的：逾時時遠端可能已經更新
    （第一版 red-team 實測），所以訊息不得保證「沒有公開」或「已完成」。
    五條處理指示都要在：訊息是固定文字，各條由使用者依診斷自己對照；每條用只有
    它才有的字樣斷言，少任何一條都會紅。
    """
    fake = FakeGit([(READ, 0, _tag_line(), ""), (PUSH, rc, "", stderr)])
    monkeypatch.setattr(rel, "run", fake)
    problem = rel.do_release("9.9.9", COMMIT, "")
    fake.done()                                   # 序列裡沒有 gh：多呼叫就 raise
    assert "rc=%d" % rc in problem, problem
    assert stderr in problem, "原始診斷沒帶出來：" + problem
    for must in ("已被別的 tag 占用", "先整合遠端變更", "先處理遠端設定",
                 "pre-push 守衛因內容擋下", "其他（連線、認證、逾時）"):
        assert must in problem, "少了這條處理指示：%s\n%s" % (must, problem)
    for never in ("已完成", "沒有生效", "尚未公開"):
        assert never not in problem, "對遠端現況下了保證：%s" % never


_PREFIX_LINE = _tag_line(ref="refs/tags/v9.9.9/x")
_LOCK = "fatal: cannot lock ref 'refs/tags/v9.9.9': 'refs/tags/v9.9.9/x' exists"


@pytest.mark.parametrize("steps,must", [
    ([(READ, 128, "", "fatal: bad config line 3")],
     ["無法讀取本機 tag", "rc=128", "fatal: bad config line 3"]),
    ([(READ, 0, "", ""), (MAKE_TAG, 0, "", ""), (READ, 128, "", "fatal: oops")],
     ["無法讀取本機 tag", "rc=128", "fatal: oops"]),
    ([(READ, 0, "", ""), (MAKE_TAG, 0, "", ""), (READ, 0, "", "")],
     ["仍讀不到"]),
    ([(READ, 0, "", ""), (MAKE_TAG, 128, "", "error: gpg failed to sign the data")],
     ["建立本機 tag", "rc=128", "gpg failed to sign"]),
    # 只有前綴同名的 ref：該行即使型態、指向、名字全對，也不得被當成本版的 tag。
    ([(READ, 0, _PREFIX_LINE, ""), (MAKE_TAG, 128, "", _LOCK)],
     ["建立本機 tag", "cannot lock ref"]),
    ([(READ, 0, _tag_line(target=OTHER), "")],
     ["不是本 commit 的直接 annotated tag", OTHER, "下一個版號"]),
], ids=["read-fails", "reread-fails", "still-missing", "tag-a-gpg-fails",
        "prefix-only", "points-elsewhere"])
def test_rg28_a_tag_that_cannot_be_verified_is_never_pushed(monkeypatch, steps, must):
    """RG28：本機 tag 讀不到、建不起來、或不是本 commit 的 tag → 一律不推送。

    驗證全部在 push 之前，序列裡沒有 push：任何一例走到 push 都會當場 raise。
    「讀不到」與「確定不符」分開說，因為暫時性的讀取錯誤不該引導人換版號；
    兩者都不叫人手動 `git tag -d`（MAINTAINING 禁止手動動 tag）。
    lightweight、巢狀、別名三種用真 git 驗（RG30C），因為那三種的欄位長相
    只有真 git 給得準。
    """
    fake = FakeGit(steps)
    monkeypatch.setattr(rel, "run", fake)
    problem = rel.do_release("9.9.9", COMMIT, "")
    fake.done()
    assert "本次沒有推送任何東西" in problem, problem
    for m in must:
        assert m in problem, "缺：%s\n%s" % (m, problem)
    assert "git tag -d" not in problem


@pytest.mark.parametrize("rc,stdout,blocked", [
    (0, "refs/heads/main\n", False),
    (0, "refs/heads/main-wip\n", True),     # 抓「startswith」那種寬鬆比對
    (0, "refs/heads/feature\n", True),
    (1, "", True),                            # detached HEAD：symbolic-ref -q 回 1
], ids=["main", "main-wip", "feature", "detached"])
def test_rg29_release_must_start_from_main(monkeypatch, rc, stdout, blocked):
    """RG29：不在 main 上 → 前置條件擋下；在 main 上 → 不擋。

    發佈用 SHA 推 `<commit>:refs/heads/main`。第一版 red-team 實測：在 feature
    分支上 commit 之後跑發佈，會把未合併的分支直接快轉成公開的 main——那是
    合法快轉，不加 force 擋不住，只能在前置條件問清楚。
    其餘前置條件全部放行，唯一能讓結果改變的就是目前所在的分支。
    """
    def fake_run(args, **kw):
        if args[:2] == ["git", "symbolic-ref"]:
            assert args == ["git", "symbolic-ref", "-q", "HEAD"], args
            return SimpleNamespace(returncode=rc, stdout=stdout, stderr="")
        assert args[:3] == ["gh", "auth", "status"], "未預期的呼叫：%r" % (args,)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(rel, "run", fake_run)
    monkeypatch.setattr(rel, "check_tests", lambda: ("", "9 passed"))
    monkeypatch.setattr(rel, "check_clean_tree", lambda: "")
    monkeypatch.setattr(rel, "check_version_matches", lambda v: "")
    monkeypatch.setattr(rel, "check_review", lambda c, o: "")
    monkeypatch.setattr(rel, "head_commit", lambda: COMMIT)
    problems, _, _ = rel.preflight("9.9.9", "")
    hit = [p for p in problems if "請在 main 上發佈" in p]
    assert bool(hit) == blocked, problems
    assert len(problems) == len(hit), "混進了別的問題，這條沒在測它該測的：%r" % problems


# ── 真 git（推到暫存 bare，不碰網路）──────────────────────────────────────
_GIT_SUBCMDS = {"init", "config", "commit", "tag", "push", "remote", "rev-parse",
                "for-each-ref", "cat-file", "update-ref", "merge-base"}
_BANNED_ARG_PREFIXES = ("--file", "--global", "--system", "--blob", "--git-dir",
                        "--work-tree", "--config-env", "--namespace", "--exec-path",
                        "--force", "--mirror")


class RealGitBox:
    """真 git 的隔離箱：所有 git 呼叫都經這裡，違反隔離就在**執行之前** raise。

    為什麼要這麼多層：抗辯實測過的逃逸——hook 環境帶進來的 GIT_DIR／
    GIT_COMMON_DIR／GIT_CONFIG_PARAMETERS、`-C <外層>`、多個 pushurl、
    `--config-env`、改掉白名單變數的值——都曾在 scratch 裡把外層 repo 寫壞或
    推到誘餌。最後一道是 GIT_ALLOW_PROTOCOL=file：本 repo 的 origin 是 SSH，
    即使前面全部失守也推不出去。
    保證的範圍：推不到暫存 bare 以外，且上述實測過的路徑都在寫入前擋下；
    不宣稱擋得住「測試碼自己故意用其他子命令選項寫外層」。
    """

    def __init__(self, tmp_path, monkeypatch):
        root = tmp_path.resolve()
        self.root = root
        empty = root / "empty"
        hooks = root / "nohooks"
        empty.mkdir()
        hooks.mkdir()
        gcfg = root / "gitconfig"
        gcfg.write_text("", encoding="utf-8")
        for k in list(os.environ):
            if k.startswith("GIT_"):
                monkeypatch.delenv(k)
        self.env = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(gcfg),
                    "GIT_CEILING_DIRECTORIES": str(root), "GIT_ALLOW_PROTOCOL": "file",
                    "GIT_TERMINAL_PROMPT": "0"}
        for k, v in self.env.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("HOME", str(root))
        monkeypatch.setenv("LC_ALL", "C")
        self.work = root / "work"
        self.bare = root / "bare.git"
        monkeypatch.setattr(rel, "ROOT", str(self.work))       # 任何 git 指令之前
        monkeypatch.setattr(rel, "ATTEST_DIR", str(root / "attest"))
        self.real = rel.run
        self.log = []
        self.gh_calls = []
        self.gh_results = []
        monkeypatch.setattr(rel, "run", self)
        self.git(["init", "--bare", "-b", "main", "--template=" + str(empty),
                  str(self.bare)], cwd=root)
        self.git(["init", "-b", "main", "--template=" + str(empty), str(self.work)],
                 cwd=root)
        for k, v in (("user.name", "t"), ("user.email", "t@example.invalid"),
                     ("commit.gpgsign", "false"), ("tag.gpgsign", "false"),
                     ("core.hooksPath", str(hooks))):
            self.git(["config", k, v])
        self.git(["remote", "add", "origin", str(self.bare)])
        self.c0 = self.commit("c0")
        self.git(["push", "origin", self.c0 + ":refs/heads/main"])
        self.c1 = self.commit("c1")

    # ── 攔截層 ──
    def __call__(self, args, **kw):
        args = list(args)
        if args[0] == "gh":
            self.gh_calls.append(args)
            rc, err = self.gh_results.pop(0) if self.gh_results else (0, "")
            return SimpleNamespace(returncode=rc, stdout="", stderr=err)
        self._check(args, kw)
        self.log.append(args)
        return self.real(args, **kw)

    def _check(self, args, kw):
        assert args[0] == "git", "非 git 的呼叫：%r" % (args,)
        # argv[1] 必須是子命令：等於禁掉所有 git 全域選項（-C、-c、--git-dir…）
        assert args[1] in _GIT_SUBCMDS, "不允許的子命令或全域選項：%r" % (args,)
        bad = [a for a in args[2:] if a.startswith(_BANNED_ARG_PREFIXES)]
        assert not bad, "不允許的選項：%r" % (bad,)
        assert "env" not in kw, "不得覆寫環境：%r" % (args,)
        git_env = {k: v for k, v in os.environ.items() if k.startswith("GIT_")}
        assert git_env == self.env, "GIT_ 環境變數被動過：%r" % (git_env,)
        assert os.environ.get("HOME") == str(self.root), "HOME 被動過"
        assert os.environ.get("LC_ALL") == "C", "LC_ALL 被動過"
        cwd = pathlib.Path(kw.get("cwd", rel.ROOT)).resolve()
        assert cwd.is_relative_to(self.root), "cwd 在暫存根之外：%s" % cwd
        if args[1] != "init":
            probe = self.real(["git", "rev-parse", "--absolute-git-dir"], cwd=str(cwd))
            gitdir = pathlib.Path((probe.stdout or "").strip()).resolve()
            assert probe.returncode == 0 and gitdir.is_relative_to(self.root), (
                "實際 gitdir 在暫存根之外：%s" % gitdir)
        if args[1] == "push":
            dest = [a for a in args[2:] if not a.startswith("-")][0]
            assert dest == "origin", "推送目的地不是 origin：%r" % (args,)
            out = self.real(["git", "remote", "get-url", "--push", "--all", "origin"],
                            cwd=str(cwd))
            urls = (out.stdout or "").splitlines()
            assert out.returncode == 0 and len(urls) == 1, "push url 不是恰好一個：%r" % urls
            assert pathlib.Path(urls[0]).resolve() == self.bare.resolve(), urls

    # ── 夾具小工具 ──
    def git(self, argv, cwd=None):
        kw = {"cwd": str(cwd)} if cwd else {}
        out = self(["git"] + argv, **kw)
        assert out.returncode == 0, "夾具指令失敗：%r\n%s" % (argv, out.stderr)
        return (out.stdout or "").strip()

    def commit(self, msg):
        self.git(["commit", "--allow-empty", "-m", msg])
        return self.git(["rev-parse", "HEAD"])

    def remote(self, ref):
        out = self(["git", "rev-parse", "-q", "--verify", ref], cwd=str(self.bare))
        return (out.stdout or "").strip() if out.returncode == 0 else ""

    def release(self):
        """跑一次 do_release，回 (訊息, 這次的 git 呼叫)。與夾具的呼叫分開記。"""
        start = len(self.log)
        msg = rel.do_release("9.9.9", self.c1, "")
        return msg, self.log[start:]


def _pushes(calls):
    return [c for c in calls if c[1] == "push"]


def test_rg30a_a_conflicting_remote_tag_rejects_the_whole_push(tmp_path, monkeypatch):
    """RG30A：遠端同名 tag 指向別處 → 整筆推送被拒，遠端 main 也不動（atomic）。

    拿掉 `--atomic` 時，git 會推上 main、只拒 tag——留下「main 已公開、沒有 tag
    也沒有 Release」的半套（第二版 red-team 實測）。訊息必須帶 git 的實際拒絕行，
    而那一行含 `-> v9.9.9 (already exists)`，固定說明文字裡沒有。
    """
    box = RealGitBox(tmp_path, monkeypatch)
    box.git(["tag", "-a", "v9.9.9", "-m", "someone else's", box.c0])
    box.git(["push", "origin", "refs/tags/v9.9.9:refs/tags/v9.9.9"])
    box.git(["tag", "-d", "v9.9.9"])
    before_main, before_tag = box.remote("refs/heads/main"), box.remote("refs/tags/v9.9.9")
    assert before_main == box.c0 != box.c1, "前置：遠端 main 必須落後"
    box.git(["merge-base", "--is-ancestor", box.c0, box.c1])
    assert before_tag, "前置：遠端要先有衝突的 tag"

    msg, calls = box.release()
    assert len(_pushes(calls)) == 1, "沒有真的走到推送：%r" % (calls,)
    assert re.search(r"\[rejected\]\s+\S+\s+->\s+v9\.9\.9\s+\(already exists\)", msg), msg
    assert box.remote("refs/heads/main") == before_main, "tag 被拒，main 卻推上去了"
    assert box.remote("refs/tags/v9.9.9") == before_tag
    assert box.gh_calls == [], "推送失敗後仍去建 Release"


def test_rg30b_main_and_the_annotated_tag_land_and_a_rerun_only_adds_the_release(
        tmp_path, monkeypatch):
    """RG30B：正常發佈 → 遠端 main＝本 commit、tag＝本機同一個 annotated 物件；
    gh 失敗後用同一組參數重跑 → 推送是無動作，只補建 Release。

    夾具故意開 push.followTags 與 push.recurseSubmodules=only：前者拿掉
    `--no-follow-tags` 時會把 v9.9.9-extra 帶上去；後者拿掉
    `--no-recurse-submodules` 時 git 不推主 repo 卻回 rc 0（第五版 red-team 實測）。
    """
    box = RealGitBox(tmp_path, monkeypatch)
    box.git(["tag", "-a", "v9.9.9-extra", "-m", "not part of this release", box.c1])
    box.git(["config", "push.followTags", "true"])
    box.git(["config", "push.recurseSubmodules", "only"])
    assert box.remote("refs/heads/main") == box.c0 != box.c1, "前置：遠端 main 必須落後"
    assert not box.remote("refs/tags/v9.9.9-extra")

    box.gh_results = [(1, "HTTP 502"), (0, "")]
    msg, calls = box.release()
    assert "main 與 tag 已推上 origin" in msg, msg
    local_tag = box.git(["rev-parse", "refs/tags/v9.9.9"])
    assert local_tag != box.c1, "本機 tag 必須是 annotated 物件"
    assert box.remote("refs/heads/main") == box.c1, "main 沒推上去"
    assert box.remote("refs/tags/v9.9.9") == local_tag, "遠端 tag 不是本機驗過的那個物件"
    assert box.git(["cat-file", "-t", local_tag], cwd=box.bare) == "tag"
    assert not box.remote("refs/tags/v9.9.9-extra"), "把別的 tag 一起帶出去了"
    assert "--verify-tag" in box.gh_calls[0]

    msg, calls = box.release()
    assert msg == "", msg
    assert not any(c[1] == "tag" for c in calls), "重跑時重建了 tag"
    assert box.remote("refs/tags/v9.9.9") == local_tag
    assert len(box.gh_calls) == 2


@pytest.mark.parametrize("kind", ["lightweight", "nested", "alias"])
def test_rg30c_a_tag_that_is_not_this_commits_direct_annotated_tag_is_not_pushed(
        tmp_path, monkeypatch, kind):
    """RG30C：本機同名 tag 是 lightweight、巢狀、或別名 → 不推送。

    每例只違反一個條件。巢狀是第五版被推翻的那一處：`%(*objectname)` 會一路
    剝到 commit，所以「最終指向對的 commit」的巢狀 tag 原本會通過。用真 git
    是因為 lightweight 那一行的空欄（結尾三個 tab）只有真輸出才準。
    """
    box = RealGitBox(tmp_path, monkeypatch)
    if kind == "lightweight":
        box.git(["tag", "v9.9.9", box.c1])
    elif kind == "nested":          # 外層名字＝v9.9.9，只違反「直接指向 commit」
        box.git(["tag", "-a", "inner", "-m", "inner", box.c1])
        box.git(["tag", "-a", "v9.9.9", "-m", "outer", "inner"])
    else:                           # 直接指向本 commit，只違反「物件內名字」
        box.git(["tag", "-a", "rc1", "-m", "rc1", box.c1])
        box.git(["update-ref", "refs/tags/v9.9.9", box.git(["rev-parse", "refs/tags/rc1"])])
    msg, calls = box.release()
    assert "不是本 commit 的直接 annotated tag" in msg, msg
    assert _pushes(calls) == [], "驗證不過卻推送了"
    assert box.remote("refs/heads/main") == box.c0


def test_rg30e_a_ref_named_like_the_commit_id_cannot_redirect_what_is_pushed(
        tmp_path, monkeypatch):
    """RG30E：本機有一個名字剛好是審過 commit 完整 OID 的分支時，推的仍是那個 commit。

    git 解析 push 來源時先比對 ref 名稱、找不到才當成物件名（Codex 第六輪引
    git 2.53 remote.c 的 match_explicit_lhs）。`refs/heads/<A 的 OID>` 指向未審查
    的 B 時，`<A>:refs/heads/main` 實際推的是 B——遠端 main＝B、tag 卻指向 A。
    來源寫成 `<A>^{commit}`／`<tag>^{tag}` 才強制當物件解析。
    """
    box = RealGitBox(tmp_path, monkeypatch)
    c2 = box.commit("unreviewed")
    box.git(["update-ref", "refs/heads/" + box.c1, c2])     # 名字＝c1 的 OID，指向 c2
    box.git(["update-ref", "refs/heads/main", box.c1])      # HEAD 回到審過的 c1
    assert box.git(["rev-parse", "HEAD"]) == box.c1
    msg, _ = box.release()
    assert box.remote("refs/heads/main") == box.c1, (
        "推上去的不是審過的 commit：%s（訊息：%s）" % (box.remote("refs/heads/main"), msg))


_ESCAPES = {"global-option": "不允許的子命令", "banned-option": "不允許的選項",
            "env-override": "不得覆寫環境", "GIT_DIR": "GIT_ 環境變數被動過",
            "changed-value": "GIT_ 環境變數被動過", "home-changed": "HOME 被動過",
            "lc-all-changed": "LC_ALL 被動過", "cwd-outside": "cwd 在暫存根之外",
            "gitdir-redirect": "實際 gitdir 在暫存根之外",
            "dest-not-origin": "推送目的地不是 origin",
            "two-push-urls": "push url 不是恰好一個"}


@pytest.mark.parametrize("escape", list(_ESCAPES))
def test_rg30d_the_isolation_box_blocks_each_measured_escape_before_running_it(
        tmp_path, monkeypatch, escape):
    """RG30D：RealGitBox 的每一道檢查都要咬得到人——故意違反就在執行前 raise。

    守衛只有在「故意違反會紅」時才算守衛。每一例只違反一道檢查，十一例涵蓋
    `_check` 的全部檢查；其中 -C、GIT_DIR、改掉白名單變數的值、`--file`、多個
    pushurl 是抗辯在 scratch 實測過、曾經寫壞外層 repo 或推到誘餌的路徑。
    斷言兩件事：raise 了，而且那條指令沒有被執行（log 沒有增加；誘餌 bare
    沒有收到任何 ref）。
    """
    box = RealGitBox(tmp_path, monkeypatch)
    outside = str(tmp_path.parent)
    cmd, kw = ["git", "config", "redteam.x", "1"], {}
    if escape == "global-option":
        cmd = ["git", "-C", outside, "config", "redteam.x", "1"]
    elif escape == "banned-option":
        cmd = ["git", "config", "--file", os.path.join(outside, "x.cfg"), "redteam.x", "1"]
    elif escape == "env-override":
        kw = {"env": dict(os.environ)}
    elif escape == "GIT_DIR":
        monkeypatch.setenv("GIT_DIR", outside)
    elif escape == "changed-value":
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.path.join(outside, "gitconfig"))
    elif escape == "home-changed":
        monkeypatch.setenv("HOME", outside)
    elif escape == "lc-all-changed":
        monkeypatch.setenv("LC_ALL", "zh_TW.UTF-8")
    elif escape == "cwd-outside":
        kw = {"cwd": outside}
    elif escape == "gitdir-redirect":     # cwd 在箱內，但 .git 檔把 gitdir 轉到箱外
        gf = box.root / "gf"
        gf.mkdir()
        (gf / ".git").write_text("gitdir: " + os.path.join(outside, "elsewhere"),
                                 encoding="utf-8")
        kw = {"cwd": str(gf)}
    elif escape == "dest-not-origin":
        cmd = ["git", "push", str(box.bare), box.c1 + ":refs/heads/main"]
    else:
        decoy = box.root / "decoy.git"
        box.git(["init", "--bare", "-b", "main", str(decoy)], cwd=box.root)
        box.git(["config", "--add", "remote.origin.pushurl", str(box.bare)])
        box.git(["config", "--add", "remote.origin.pushurl", str(decoy)])
        cmd = ["git", "push", "origin", box.c1 + ":refs/heads/main"]
    before = len(box.log)
    with pytest.raises(AssertionError, match=_ESCAPES[escape]):   # 必須是這道檢查擋的
        box(cmd, **kw)
    assert len(box.log) == before, "擋下之前就執行了"
    if escape == "two-push-urls":
        assert not box.git(["for-each-ref"], cwd=box.root / "decoy.git"), "誘餌收到了 ref"


def test_rg31_a_release_that_skipped_review_can_be_resumed_with_the_same_arguments(
        tmp_path, monkeypatch, capsys):
    """RG31：帶 --override-review 首發、gh 失敗 → 用同一組參數重跑能補完；
    不帶 override 重跑 → 被審查檢查擋下、不推送。

    經 `main()` 走完整路徑：真的 check_review、write_attestation、do_release，
    只替換外圍（工作區、版號、全套測試、HEAD）。失敗只設在 `gh release create`
    ——設在 `gh auth status` 會停在前置條件，根本走不到要測的那一步。
    """
    monkeypatch.setattr(rel, "ATTEST_DIR", str(tmp_path))
    monkeypatch.setattr(rel, "head_commit", lambda: COMMIT)
    monkeypatch.setattr(rel, "check_clean_tree", lambda: "")
    monkeypatch.setattr(rel, "check_version_matches", lambda v: "")
    monkeypatch.setattr(rel, "check_tests", lambda: ("", "9 passed"))
    pre = [(["git", "symbolic-ref", "-q", "HEAD"], 0, "refs/heads/main\n", ""),
           (["gh", "auth", "status"], 0, "", "")]
    args = ["9.9.9", "--override-review", "--reason", "prod outage"]

    fake = FakeGit(pre + [(READ, 0, "", ""), (MAKE_TAG, 0, "", ""),
                          (READ, 0, _tag_line(), ""), (PUSH, 0, "", ""),
                          (GH, 1, "", "HTTP 502")])
    monkeypatch.setattr(rel, "run", fake)
    assert rel.main(args) == 1
    fake.done()
    assert "main 與 tag 已推上 origin" in capsys.readouterr().out

    fake = FakeGit(pre + [(READ, 0, _tag_line(), ""), (PUSH, 0, "", ""), (GH, 0, "", "")])
    monkeypatch.setattr(rel, "run", fake)
    assert rel.main(args) == 0, capsys.readouterr().out
    fake.done()                                   # 序列裡沒有 tag -a：重建就 raise
    notes = fake.calls[-1][fake.calls[-1].index("--notes") + 1]
    assert "ADVERSARIAL_REVIEW_BYPASSED" in notes and "prod outage" in notes, notes
    doc = rel.read_attestation(COMMIT)
    assert doc["adversarial_review_bypassed"] and doc["bypass_reason"] == "prod outage"

    fake = FakeGit(pre)                           # 不帶 override：走不到推送
    monkeypatch.setattr(rel, "run", fake)
    assert rel.main(["9.9.9"]) == 1
    fake.done()
    assert "不是審查" in capsys.readouterr().out
