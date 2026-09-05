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
最後執行：2026-09-06 00:29 → 17 passed ✅（全套 239 passed）

驗收邊界——本檔測的是**前置條件的判定**，不是 `git push` 與 `gh release create`
本身。那兩者會對外送出，不可能在測試裡驅動；它們的正確性由 RG3 的同型檢查
（tag 指向的 commit 必須等於被審查的 commit）在正式發佈時當場驗。

✅ 已驗收（本檔涵蓋）
  RG1-RG11 → 每條「必須被擋下」都有配對的「必須仍然做得到」，
    因為一個「什麼都擋」的閘也會讓前者全綠而讓專案完全發不出東西
  RG12／RG13 → 接線：腳本在文件寫明的發佈路徑上，而且真的跑得起來
⏳ 待驗收（本檔未涵蓋）
  `do_release()` 的對外動作（tag 推送、Release 建立）：會真的送到 GitHub，
    無法在測試中驅動。解鎖條件＝在一次真實發佈中觀察它完成，並確認
    `gh release list` 顯示該版為 Latest（README 的發佈 checklist 步驟）。
  server 端驗證（GitHub workflow 檢查 reviewed_commit == tag SHA）：
    本 repo 目前沒有 `.github/workflows`（實查：`git ls-files .github` 無輸出）。
    外審建議加，但那是把信任邊界從本機移到 server 的另一項工程。
    解鎖條件＝決定要不要引入 CI，以及由誰持有 attestation 的真實來源。
"""
import json
import os
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
    rel.write_attestation(commit, {"skeptic": "REFUTED"}, "ship", "9 passed")
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
    monkeypatch.setattr(rel, "check_version_matches", lambda v: "")
    monkeypatch.setattr(rel, "check_review", lambda c, o: "")
    problems, _, summary = rel.preflight("9.9.9", "")
    assert any("測試沒有全綠" in p for p in problems), "紅燈沒有擋下發佈"
    assert "1 failed" in summary, "擋下的理由沒有帶著摘要行"


def test_rg7b_a_green_suite_does_not_block(monkeypatch):
    """RG7b：RG7 的配對——全綠時前置條件必須通過。

    沒有這條，一個「永遠回報有問題」的 preflight 也會讓 RG7 綠。
    """
    monkeypatch.setattr(rel, "check_tests", lambda: ("", "222 passed in 19.77s"))
    monkeypatch.setattr(rel, "check_clean_tree", lambda: "")
    monkeypatch.setattr(rel, "check_version_matches", lambda v: "")
    monkeypatch.setattr(rel, "check_review", lambda c, o: "")
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
