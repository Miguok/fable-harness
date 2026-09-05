# 維護 Fable Harness

[English](MAINTAINING.md) &nbsp;·&nbsp; **繁體中文**

給本 repo 維護者的備註。使用這個 kit 不需要這份文件——那請看 [README](README.md) 與 [INSTALL.md](INSTALL.md)。

## 審查動到 `.claude/wiring-guards` 的 PR

那個檔案是一份 shell 指令清單，而 pre-commit runner 會對它的每一行做 `eval`。
改動它＝改動「合併之後，每一個 commit 的人機器上會跑什麼」——請用讀建置腳本的
方式讀它，不要當成一般設定值。`.claude/hooks/wiring_runner.sh` 本身同理。

## 審查動到 `.claude/fable-verifier` 的 PR

那個檔案列出「哪些指令變綠就算目標達成」。在裡面加一行等於**開一個豁免**：
宣告一條永遠會過的指令，目標關卡就不再升級，而且是靜默的。它在工作目錄裡、
會隨 clone 傳遞，所以請比照 `.claude/wiring-guards` 來讀——那是在改「這道閘
接受什麼」，不是改一個設定值。

這是刻意的取捨。它取代的是由閘**自己推論**「寬指令的綠涵蓋窄指令的紅」，
而那個推論被實測出六種算錯的形態。宣告至少要求 repo 把話講出來，寫在一個
審查者看得到的檔案裡。

## 讓貢獻者名單保持乾淨（不長 `noreply` / Claude phantom）

Claude Code 預設會在它協助寫的 commit 尾端附上一行 `Co-Authored-By: Claude <noreply@anthropic.com>`。GitHub 會把這行 trailer 當成一位貢獻者，於是 repo 的 **Contributors** 側欄會冒出一個不是真人的 `noreply` / `claude` 項目。兩層防線把它擋掉。

### 1. 你自己的 commit——已自動處理

`.claude/settings.json` 設定：

```json
"attribution": { "commit": "", "pr": "" }
```

這告訴 Claude Code：在本 repo 建立的 commit 與 PR 不要附加 co-author trailer（或 PR 頁尾），所以你自己的 commit 不會生 phantom。每次 commit 都不用特別處理。

### 2. 貢獻者的 PR——合併 SOP

你無法控制貢獻者用的設定，所以他們的 PR commit 可能仍帶著 Claude trailer。在**合併時**把它拿掉。

**收 PR 一律用「Squash and merge」（壓縮合併）**——這是唯一能讓你編輯最終 commit 訊息的合併方式。

1. 在 PR 頁，點合併鈕的下拉箭頭，選 **Squash and merge**。
2. 在可編輯的訊息框裡，**刪掉 email 為 `noreply@anthropic.com` 的那一行**，例如：
   ```
   Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
   ```
   顯示名稱可能是 `Claude Opus …` 或 `Claude Fable 5`——認 `noreply@anthropic.com` 這個位址，別認名字。
3. 若有**真人**的 `Co-authored-by:` 行（例如 `... <某人@users.noreply.github.com>`），**要保留**——那是真正的協作者，應該被記功。
4. 確認壓縮合併。

真人 PR 作者仍會被記功——他是 commit 的**作者（author）**，與任何 co-author 行無關。被拿掉的只有 Claude phantom。

CLI 等效指令：

```
gh pr merge <PR> --squash --body "<不含 Claude 那行的乾淨訊息>"
```

### 為什麼不用其他合併方式

**Create a merge commit** 與 **Rebase and merge** 會原封不動照搬 PR 的原始 commit，Claude trailer 因此存活、phantom 又出現。只有 **Squash and merge** 能讓你編輯訊息。

### 這套做法「不會」做到的事

- **不溯及既往。** 已經合併進去的 commit 仍帶著它當初的 trailer。要清那些得改寫已發佈的歷史，而我們刻意不做——那會弄壞開啟中的 PR 與 forks。
- **不要**為了避開 trailer 就把一個好的 PR 關掉、自己重寫。那等於抹掉一位真實貢獻者。請照收、合併，然後只刪那一行。

## 發佈

`scripts/release.py` 是唯一支援的發佈方式。**不要**手動下 `gh release create`、
`git tag` 或 `git push --tags`。

```sh
# 1. 跑完抗辯審查後，把結果綁在那個 commit 上
python scripts/release.py --attest \
  --lenses "skeptic:REFUTED,red-team:REFUTED,simplifier:REFUTED" \
  --judge "ship"

# 2. 乾跑——只驗前置條件
python scripts/release.py 1.5.0 --check

# 3. 發佈
python scripts/release.py 1.5.0
```

工作區不乾淨、`VERSION` 對不上、`CHANGELOG.md` 沒有該版章節、測試沒全綠，或
**這個 commit** 沒有抗辯審查紀錄，它都會拒絕。最後一項是 attestation 要存
`reviewed_commit` 的原因：審查完再改一行就發佈，只問「有沒有審查」的檢查會
放行，而那一行正是沒有人看過的那一行。

為什麼做成腳本而不是攔發佈指令的 hook：`gh release create`、`git push --tags`、
GitHub API、網頁介面是一個無限的語法面，接線閘門已經在 `--no-verify` 上花了
三個版本學到這件事。穩定的是**產出物的前置條件**，不是別人打字的形狀。

### 緊急出口

```sh
python scripts/release.py 1.5.1 --override-review --reason "critical security rollback"
```

理由是必填的，會同時寫進 attestation 與發佈說明，並標上
`ADVERSARIAL_REVIEW_BYPASSED`。保留它的理由是：沒有緊急出口時，真正緊急的人
會發明更髒的旁路，而那些旁路不會留下任何紀錄。
