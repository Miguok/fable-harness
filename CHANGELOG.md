# Changelog

All notable changes to Fable Harness are recorded here.

This kit follows [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`:

- **MAJOR** — a breaking change to the protocol contract (a hook/skill/agent removed or renamed, or an incompatible change to how the protocol is injected or how agents are dispatched) that would require users to re-install or change their setup.
- **MINOR** — a backward-compatible addition (a new hook, skill, agent, or governance rule) that existing installs keep working alongside.
- **PATCH** — a backward-compatible fix or wording change (a bug fix in a hook, a clarified rule, a typo).

The current version is also kept in [VERSION](VERSION).

## [Unreleased]

## [1.5.0] — 2026-09-06

外部審查（ChatGPT GPT-5.6 Sol）讀了 v1.4.3 之後給的判定是 REQUEST CHANGES，而它
最重要的一條指出：**協議寫「計數對象是目標」，實作根本沒有目標這個東西。** 本版
把那句話補成可以實作的定義，並把「未經抗辯不得發佈」從文字規則變成機械閘。

### Added

- **目標關卡現在真的認得出「同一個目標」**（協議新增 §4b-1）。在此之前跨回合
  累加的是**單一全域計數**：目標 X 失敗一次、接著改做無關的目標 Y 又失敗，閘會
  宣稱「這個目標已經連敗兩次」——兩個不同的工作被串成同一條階梯，中間沒有任何
  綠燈把它斷開。現在**每個測試目標各自計數**：不同的鍵互不影響，交替跑窄／寬指令時各自累加。

- **`.claude/fable-verifier`：repo 可以宣告哪一條指令算「驗過了」。** 它變綠就
  收束整段目標，連還沒各自轉綠的窄範圍測試也一併收掉。這解決了除錯與突變測試的
  必然節奏——「跑窄的 → 紅 → 修好 → 用全套驗 → 綠」，而綠燈落在另一個鍵上。
  1.4.x 曾試著讓程式自己推論「寬指令涵蓋窄指令」，抗辯實測出六種會把**真紅燈**
  靜默清掉的情況而退回；差別在誰說了算：推論是程式猜，宣告是 repo 自己講。
  權威綠必須**出現在紅之後**才算數，否則「全套綠 → 改壞 → 窄的紅」會被讀成達成。

- **`scripts/release.py`：發佈是一筆交易，不是一條指令。** 工作區不乾淨、
  `VERSION` 對不上、`CHANGELOG` 沒有該版章節、測試沒全綠，或**這個 commit** 沒有
  抗辯審查紀錄，它都會拒絕。審查紀錄綁 `reviewed_commit`：審查完再改一行就發佈，
  只問「有沒有審查」的檢查會放行，而那一行正是沒有人看過的那一行。
  不做成攔 `gh release create` 的 hook，是因為那是一個無限的語法面（API、網頁、
  各種別名），而接線閘門已經在 `--no-verify` 上花三個版本學過這件事。
  緊急出口 `--override-review --reason "…"` 必須填理由，並在發佈說明標上
  `ADVERSARIAL_REVIEW_BYPASSED`——沒有出口時，真正緊急的人會發明不留紀錄的旁路。
  ⚠ 破窗的**痕跡不是審查**：那筆紀錄不會讓下一次發佈免審，而 `--check` 乾跑
  不留下任何紀錄。兩者都是發佈前抗辯抓到的（見下方）。

### Fixed

- **提示檔不再從 repo 路徑推導檔名。** 舊做法把非英數字元全換成底線，於是
  `x/evil-a`、`x/evil_a`、`x/evil/a` 撞成同一個檔名。1.4.1 補了讀取端的比對，
  但**覆寫**面補不起來：兩個都沒 opt-in 的碰撞 repo，後寫的必然蓋掉先寫的，而讓
  其中一方「因為這是別人的檔案」不寫，那一方就永遠沒有提示。改問
  `git rev-parse --git-path` 之後，主 repo 拿到 `.git/fable/…`、linked worktree
  拿到各自的 `.git/worktrees/<name>/fable/…`——碰撞在結構上不可能發生，而不是
  被一道檢查擋住。同時兩端都問同一個來源，1.4.1 那種「Python 逐字元 vs `tr`
  逐位元組」的雙端分歧也一併消失。`.git` 不會被 clone 帶走，所以惡意 repo 放不
  進東西，這正是提示檔不能搬進工作目錄的那個約束。

- **兩個 session 同時擱置不再遺失一筆**（v1.4.3 記為已知限制，實測 5/5）。狀態的
  讀改寫加了鎖檔。擱置項是「這件事交回使用者拍板」的唯一載體，消失之後那個目標
  與被放棄分不出差別。⚠ 拿不到鎖時照樣往下做：一次遺失的更新比一個結束不了的
  回合便宜。

- **`.fable/.gitignore` 一定會被寫出來。** 鎖、狀態寫入、發佈紀錄三處都會建這個
  目錄，而「只在自己建立時才寫 `.gitignore`」的判斷若分散，先跑到的那個會讓其餘
  永遠判 False——狀態檔就開始出現在使用者的 `git status`。goal_gate 內部已收斂成
  一個函式；`scripts/release.py` **另有一份**（它不 import hook），兩份寫的是同一
  條規則但不會互相同步。這是刻意的邊界（發佈腳本不依賴 hook），代價寫在這裡。

### Changed

- 目標關卡**維持硬擋，不降級為勸告**。外部審查主張硬阻擋器需要極高精準度、達不到
  就該降級；採相反決定的理由是：降成提醒之後就沒有東西逼人停下來，而「文字規則
  擋不住寫規則的人」在 1.4.1／1.4.2 已兌現兩次。精準度改由 §4b-1 的定義負責。

### 發佈前抗辯抓到的（本版自己的流程救了本版）

三個獨立鏡頭在發佈前審查本版，**三個都判 REFUTED**，其中一條是 P0：

- 🔴 **第一版的「目標身分」把整條階梯關掉了。** 當時定成「使用者送出一則 prompt
  ＝一段新目標」，而 Stop 每個回合最多累加一次——於是使用者每說一句話就清空計數，
  永遠到不了第 2 格。實測同一個目標連續失敗四個回合，計數固定停在 1，一次都沒擋、
  沒擱置，而 239 個測試全綠。改成「目標的身分是**那個測試目標本身**」之後，實測
  1 → 2（擋，要求抗辯）→ 擱置，換成無關目標則回到 1。
  **它沒被測到的原因很具體**：新測試只寫了「不相關的目標不得串接」，沒有配對的
  「同一個目標仍必須爬得上去」——而一個「永遠歸零」的實作完全滿足前者。
- **`.fable/.gitignore` 對採用者從來不會被寫出來**：發佈腳本是第三個會建出該目錄
  的寫入者，它繞過了那條「只在自己建立時才寫」的規則。本 repo 因為根目錄
  `.gitignore` 有 `.fable/` 而看不出來——只在自己身上驗過的典型盲點。
- **緊急出口在本機不留痕**：說明文件寫「理由會寫進 attestation」，實際上 override
  路徑從來沒呼叫過寫入。唯一紀錄是 GitHub release notes，而那是同一個人事後可以
  編輯的東西。
- **tag 在驗證之前就被推出去**：不一致時，指向未審查程式的公開 tag 已經推上去了。
- **`.fable` 是一般檔案時，每次 Stop 固定停 1.5 秒**（鎖的例外處理掉進空轉）。
- **一條測不到東西的測試**：檢查工作區是否乾淨的那條，從頭到尾沒呼叫過被測函式，
  把整個函式刪掉它照樣綠。

**修完第一批之後，第二個鏡頭又在同一片區域挖出三個**——「同一個目標」這件事，
本版一共設計錯了兩次才對：

- 🔴 **窄／寬指令交替時，階梯永遠停在第 1 格。** 第二稿只記一個計數，鍵一換就
  歸 1。而「跑窄的確認這個 case、再跑全套確認沒弄壞別的」是除錯**最標準**的
  節奏，不是刁鑽輸入——實測六個回合全紅、零次擋。最終改成**每個鍵各自計數**，
  兩邊同時成立：交替的指令各自累加，無關的目標互不影響。
- 🔴 **一個再也不會重跑的舊紅鍵，永久關掉了「綠燈歸零」。** 歸零條件寫成
  「有綠**而且**沒有任何未解的紅」，於是明明中間綠過一次，閘仍宣稱「連續失敗
  兩次」。硬擋的假陽性，正是這道閘最該避免的。
- 🔴 **同一個鍵的「判不出成敗」會抹掉它先前的真紅**（違反本版自己寫的
  §4b-1 第 6 條「維持原狀」）。換 venv、檔案搬走、路徑打錯都會走到這條路。

**第二輪抗辯（第一輪的修法自己也被審一次）又挖出兩個 P0**——這正是為什麼
協議要求「連續兩輪無新發現」才算收工：

- 🔴 **緊急出口會把自己洗成合格審查。** `check_review` 原本只看 `reviewed_commit`，
  不看 `adversarial_review_bypassed`，於是一次跳過留下的紀錄會讓**下一次不帶任何
  旗標**的發佈直接放行，而發佈說明也不再標記已跳過。更糟的是 `--check` 乾跑也會
  寫紀錄——「看看而已」就足以把該 commit 永久標成已審查。留痕是這條通道獲准存在
  的唯一條件，而它把自己的痕跡洗掉了。兩個獨立鏡頭同時抓到。
- 🔴 **「舊版狀態檔接續」每天都會誤觸，讓無關的目標一紅就被擱置。** 那條相容分支
  的判準是「未解的紅剛好是空的、而計數非零」，但狀態檔沒有版本標記，而綠燈的清除
  每天都在製造這個組合：修好 A、同一回合開始做 B，B 第一次紅就繼承 A 的階梯被直接
  擱置。擱置項的說明欄是空的，於是**此後每個乾淨回合都被擋**，直到有人手動編 JSON
  ——假陽性從一次性變成黏著的。相容分支已整個刪除：從舊版升級的人那條階梯從 1
  重算，多一個回合才擋，那個代價便宜得多。

同批修掉的還有：機密遮蔽漏掉標頭式（`Authorization: Bearer …`）與引號內含空白的值，
而擱置項是**每次**開場都會重新注入的東西；追蹤上限淘汰掉的是爬最高的目標而不是最久
沒動的；擱置一個目標會清空其他目標的進度；`.fable` 是懸空連結時每次都停 1.5 秒；
型別守衛只加在三個欄位的其中一個，而這道閘自己明文要求使用者手改那個檔。

**第三輪抗辯又是兩個 P0，而且這一輪加了一個「必然有問題」的角色**——它被明令
不得回答「看起來沒問題」，必須交出可重現的缺陷。它挖到的兩條都不是本版的回歸，
而是**從 1.2.0 就在**的東西：

- 🔴 **回合邊界的判定在生產環境是反的。** 判斷「這是一則使用者輸入嗎」要求內容是
  字串，但 Claude Code 送出的使用者輸入是 **list 形**：掃本機 200 份真實 transcript，
  list 形且含文字的 436 筆裡有 427 筆是真的使用者打的字，而字串形的 539 筆幾乎全是
  harness 注入——**包括這道閘自己的擋人訊息**。於是它拒絕每一則真實輸入、卻把自己的
  擋人訊息當成新回合的開始：回合視窗不前進，舊的紅鍵每次都被重數，閘會對一個使用者
  早就放掉的目標永遠擋下去。`verify_gate` 有同一段程式碼，同批修掉。
  **而 67 條測試全綠，是因為每一個 fixture 都用那個不存在的字串形狀**——測試驗的是
  一個 Claude Code 不會產生的格式。fixture 已全數改用真實形狀。
- 🔴 **`test_key` 在第一個 `>` 或 `|` 就截斷，包括引號裡的和測試指令前面的。**
  量測 4,162 次真實測試執行，1,453 次（35%）算出的鍵完全不含測試指令；最標準的
  TDD 節奏 `cat > tests/test_x.py <<'EOF' … && pytest …` 讓每個目標都變成鍵 `'cat'`，
  三個各失敗一次的無關目標會被串成一條強制擱置。`go test -run 'A|B'` 與 `'A|Z'`
  同理。現在先找測試指令的起點、再剝管線，而且引號裡的 `|` 不算管線。

同輪另外兩個鏡頭補上的：追蹤上限的淘汰會在表滿時把**剛計數的新目標**當場刪掉
（計數永遠停在 1，而階梯自己叫人換打法＝換鍵，於是每一次正確使用都存入一個將來
餓死它的條目）；`GIT_CONFIG_COUNT/KEY_n/VALUE_n` 是 `-c` 的等價寫法，接線閘只擋了
`-c`，這條繞道實測**守衛一次都沒跑而 commit 成功**；機密遮蔽還漏 heredoc 記號、
`--key "值 含空白"`、GitLab 的 `PRIVATE-TOKEN`，而標頭規則沒有引號時會把後面的指令
整段吞掉；`.fable/` 若是 repo 自己帶進來的，`.gitignore` 永遠不會被寫；型別守衛只
掃到容器層，元素層仍能讓兩個入口同時靜默死亡。

⚠ **本輪有三條新加的守衛自己是假綠**，突變測試才抓到：斷言打在程式碼到不了的分支上、
兩種情況給同樣的數字所以分不出來、以及測試 repo 因為**別的理由**被擋而讓修法看起來
有效。第三條尤其值得記：我當時手動「驗證」過它，而那次驗證本身是假的。

**外部審查（GPT-5.6 Sol）在三輪內部抗辯之後，又找到一個 P0**——而它正好回答了
我在送審包裡問的那個問題「`-c` 與 `GIT_CONFIG_*` 之外還有沒有第三種寫法」：

- 🔴 **`git --config-env=core.hooksPath=<空目錄> commit` 讓接線閘完全失效。**
  那是 git 官方的第三條 transient config 通道，語義等同 `-c`，只是值從環境變數取。
  我自己重現確認：守衛一次都沒跑、**commit rc=0 直接成功**，而 gate 回 allow。
  第四條 `GIT_CONFIG_PARAMETERS` 同樣有效。兩條現在都會被鏡射進閘自己的探測，
  而且**只要指令裡出現 `hooksPath` 而閘解析不出來，一律擋**（fail-closed）——
  因為列舉寫法永遠慢一步。

- ⚠ **同批修正一個過度宣稱**：`wiring_gate` 的檔頭原本寫 runner「換寫法繞不過」。
  那是錯的。誠實的說法是：git 用 repo 自己的 hook path 時每次 commit 都會經過
  runner，而 PreToolUse 另外偵測常見的 runtime override、偵測不到就擋。要做到
  「提交者繞不過」，enforcement 必須在 server 端，那不在本套件範圍內。

外部審查同時指出這四輪是**同一個形狀的四次**：prompt 的形狀、測試指令的語法、
淘汰的情境、git 的設定通道——每一次都是「實作與測試圍著我當下想得到的表示法，
而真正的不變量比表示法大」。這句話已寫進 `wiring_gate.py` 的檔頭。

### 第五到七輪：26 條，然後才看見它們是同一件事

前四輪之後又跑了三輪（四個鏡頭，其中一個席位的角色是「這裡一定有問題」）。
再挖出 26 條，逐條修完、逐條附突變測試。其中比較重的幾條，都附了真實語料量測：

- **判不出成敗的輸出被當成「通過」**，而通過會把整條階梯清掉——也就是說
  「我看不懂這段輸出」被讀成「目標達成」，還順手銷毀既有證據。689 份真實
  transcript 回放：45 次階梯被清掉裡有 8 次來自這條預設，其中一次發生在第 2 格；
  1,033 筆預設通過裡有 172 筆內容是「指令移到背景執行」——執行根本還沒結束。
  順帶發現 `go test`／`dotnet test`／`mvn` 的**失敗**也被判成通過（它們的失敗行
  不含 `N failed`），紅燈讀成綠燈。現在沒有證據就是 `vacuous`（既不累加也不解除），
  並補了那些生態的明確標記表；表沒涵蓋的會讓閘變成**無作用**，而不是變成錯的。
- **停在第 2 格的紅鍵永遠不會過期**。淘汰只砍失敗一次的鍵，於是一個目標可以
  在第 2 格躺過任意多個綠燈的日子，幾天後同一條指令因為**完全不同的原因**
  失敗，就直接是第 3 格：硬擋、擱置，而且此後每個乾淨回合都被擋到有人手動編
  JSON。訊息還會宣稱「連續失敗 3 次」，那是假的。紅鍵現在有 24 小時保鮮期。
- **`git commit` 的包裝寫法整條沒被認出來**。`timeout 60 git commit --no-verify`、
  `winpty git commit -n`（`winpty` 在 Git for Windows 是預設安裝）實測都會產出
  commit、守衛一次都沒跑、閘一聲不吭。根因是「認不出來」被接到「放行」，而
  這個檔案自己的 fail-closed 兜底掛在那個早退的**下游**。
- **一列裡有多個 commit 時，只有第一個決定了 repo**。`git -C vendor commit && git
  commit -am x --no-verify` 在一個正確接線的 repo 上實測 **ALLOW**，裸的同一條
  DENY。107 條測試全綠，因為每一條都斷言在判定函式上，而判定函式是對的。
- **機密仍會落地**：`$env:GITHUB_TOKEN = "ghp_…"`（PowerShell 慣用寫法）完全沒
  遮罩，實測會寫進狀態檔並注入回下一回合的對話；`mysql -pPASS` 則是把指令分隔符
  當成值遮掉——密碼原封不動，旁邊立著一個 `***`，比不遮更危險。
- 另有：`.claude/fable-verifier` 一個非 UTF-8 位元組就讓整道閘靜默死亡（那個檔是
  文件明示要人手寫的，而 Windows 的編輯器預設不是 UTF-8）；手改狀態檔型別出錯會
  **靜默刪掉**使用者寫的備註；`--check --attest` 會留下真的審查紀錄；
  `git commit -m"訊息"`（`-m` 後不接空白）被誤擋。

⚠ **我自己寫的守衛有五條是假綠**，一併記下來，因為它們比缺陷本身更值得記：
「兩支 hook 的測試指令辨識一致」那條取樣 12 條手寫字串，而兩份**當時就已經歪了**
（一支認得 `tox`／`nox`／`deno`／`rails` 與大小寫，另一支五樣全無），五種一條都不在
我的名單裡；三條發佈閘的測試斷言在程式根本沒走到的那一格（回傳碼 1 來自版號
對不上，不是被測的那個原因），其中一條還在 pytest 裡遞迴跑整套 pytest，實測 300 秒。
最刺眼的是接線閘的 13 個 fixture **全部**把宣告檔寫在註解裡——那一整組測試模擬的
一直是「看起來接線了、實際什麼都不跑」的 hook，而那正是它要抓的病。

### 這一版相對 1.4.3 的實測效果

判準不由閘定義，三道閘各用一個**與它自己的實作無關**的預言機，同一批語料同時
餵給 `b28ea35`（1.4.3）與本版：

| 閘 | 預言機 | 1.4.3 | **1.5** |
|---|---|---|---|
| 接線閘 | 120 條生成指令**真的執行**，看 commit 有沒有成立、守衛有沒有跑（92 條是有效繞道） | 漏擋 **72**、誤擋 0 | 漏擋 **0**、誤擋 0 |
| 目標閘 | 30 份真實 transcript 回放，119 個綠回合 | 誤擋 **34（28.6%）** | 誤擋 **2（1.7%）** |
| 驗證閘 | — | 量不到（見 Known limitations） | 量不到 |

⚠ 這三個數字量的都是**誤擋**方向。「該擋而沒擋」只有接線閘量得到，因為只有它的
真相（守衛到底有沒有執行）可以向 git 問；另外兩道要先定義「這一輪算不算改了
程式碼／算不算同一個目標」，而那與閘自己的判定重疊。

⚠ 另外做過反向驗證：**1.4.3 自己的 169 條測試在本版上跑，25 條紅、20 個不同的
測試，逐條核完全部是刻意的行為改變**（提示檔改問 git、`WIRING_DECL` 接縫移除、
`--amend` 不再豁免、階梯改逐鍵計數），沒有一條是回歸。唯一要單獨講的是舊 G22：
`cd x && … && pytest t.py` 與單獨的 `pytest t.py` 現在**不算同一個目標**，因為
`cd` 進了執行 context——那是為了修「A 專案的綠清掉 B 專案的紅」而做的取捨，
方向從「誤放」換成「誤分」，不是純贏。

### 一個被我用錯誤證據撐起來的「根因」，以及它真正的大小

先講結論：**「閘會安靜地失效」是真的，但它不是那 26 條的根因。** 我第一版說是，
而支撐它的三個數字全部經不起查——這一節保留原話與更正，因為一個被錯誤證據
撐起來的根因，比沒找到根因更糟：它會讓其他類別停止被追究。

| 我當時寫的 | 實際查到的 |
|---|---|
| `verify_gate` 有 5 處 fail-open 屍檢 | **1 處**呼叫點。我 grep 的是「提到這個字串的行數」，把 docstring 與註解也算進去了 |
| 「有屍檢的那支本輪只出 2 條缺陷」 | 我引用的那個 commit **根本沒動過** `verify_gate`。⚠ 舊 CHANGELOG 沒記下是哪一個 commit，所以「哪一個」這件事我核不到，標 UNVERIFIED |
| 2 : 24 的分佈證明屍檢有效 | 不成立，**但我的第一版更正也不成立** |

⚠ 那條更正原本寫「`verify_gate` 佔三支程式碼的 10.1%、缺陷佔 7.7%，用行數就
解釋完了」。缺陷是在 `b28ea35` 那份程式上被發現的，而**當時 `verify_gate` 佔
15.0%**（181/1204 行），缺陷佔 7.7%——行數解釋不完，差了一倍。拿修完的體積去
解釋修之前的分佈是循環論證。

⚠⚠ **而「10.1% 是量在修完之後」這句話本身也是錯的**，這是同一個毛病的第三層。
逐 commit 實測（`wc -l`，三支合計）：

| commit | verify_gate 佔比 |
|---|---|
| `b28ea35`（缺陷被發現時） | 15.0% |
| `5426bbe` | **10.1%** ← 這個數字屬於這裡 |
| `cfd2908`（我寫下那句話時） | 11.1% |

我當時指的那份樹（`goal_gate` 1422 行、`wiring_gate` 852 行）是 11.1%，不是
10.1%。**我用一個量錯時點的數字，去更正另一個量錯的數字，而更正本身又指錯了樹。**

所以誠實的說法是：**兩邊都沒有證據。** 原本的因果宣稱是錯的，而我用來推翻它的
數字也是錯的（量在錯的時點）。2 : 24 這個分佈目前沒有已確立的成因，而 26 這個
分母本身也包含 `release.py` 那一批與測試檔的假綠，與「三支 hook 的程式碼」不是
同一個母體。這一整段留在這裡，是因為**用一個錯的數字去更正另一個錯的數字**，
正是這一天最該記下來的行為模式。

逐條走過 `b28ea35..HEAD` 的缺陷，經過 `except` 的傷害路徑目前找到**兩條**：
`.claude/fable-verifier` 的 cp950 位元組，以及本批自己修的 transcript 壞行
（`except json.JSONDecodeError: continue` 讓截斷的那一行整個消失，實測
verify_gate 從放行翻成擋人）。第一版寫「只有一條」，而第二條就在同一個 commit
裡——寫下那句話的時候它已經在了。其餘是正則寫錯、範圍取錯、淘汰策略錯、
遮蔽漏形態、註解與程式不符、假綠守衛，以及 `release.py` 的一批。

**那什麼才是這一天真正重複出現的？** 是**我為自己的修法配的守衛驗不到東西**。
本輪清點到的實例：兩支 hook 的測試指令辨識比對用取樣（而兩份當時已經歪了）、
接線閘 13 個 fixture 全部把宣告檔寫在註解裡、三條發佈閘的測試斷言在程式沒走到
的那一格、以及這個機制自己的 Q1／Q4／Q7。

⚠ 這裡原本寫「約 15 個」，那個數字**湊不出來**——而我第一次更正它時寫「答案是
9 或 21」，那也湊不出來。逐條算一次：

| 算法 | 式子 | 得數 |
|---|---|---|
| 13 個 fixture 各算一條 | 1 + 13 + 3 + 3 | **20** |
| 13 個 fixture 算一條 | 1 + 1 + 3 + 3 | **8** |

9 與 21 都要求第一項是 2，而同一段自己寫的是 1。所以**正確的數字是 8 或 20，
看你把那 13 個 fixture 算成一條還是十三條**。寫一個沒有清單的概數，就是這一天
一直在犯的那件事的縮小版——而它連被更正的時候都又錯了一次。

原因不在勤勞，在**突變的來源**：我做突變測試時用的是「把自己剛才的修法還原」，
而那條突變正是守衛設計時瞄準的，所以它必翻紅——證明的只是「守衛認得我的修法」。
外部鏡頭抓到的都是我沒想到的形態：把遙測整個弄死、把區塊註解掉而不是刪掉、
換一種語法寫安靜分支。差別只在那個突變不是我選的。

### 本版仍然做了「讓閘不再安靜」這件事

它值得做，只是它的份量是上面那個大小，不是我原本宣稱的：

- `note_quiet(label, exc)`：一次 fail-open 寫一行到 `.gate_fail`（UTC 時間戳、
  呼叫點標籤、例外類別）。格式化收在函式內，所以「只寫標籤與例外類別、不寫
  payload」是結構保證而不是 16 個呼叫點各自遵守的慣例——第一版是後者，而當場
  就有兩個沒遵守（一個印環境變數的值，一個寫 `str(exc)`，那會帶出絕對路徑，
  而這個檔會被注入回對話）。
- **沒有全域上限**，改成同一個標籤最多 20 行。三支 hook 寫的是同一個檔，
  所以「全域 500 行、滿了停寫」等於三支共用一個預算：實測一支壞掉灌滿之後，
  另外兩支的失效**永遠寫不進去且無人知道**——治療複製了它要治的病。
- 寫入改用 `os.open` + 單次 `os.write`（含 `O_BINARY`）。文字模式的 append
  在 Windows 上實測會掉筆：三個行程各寫一行，20 次試驗有 19 次只剩兩行，
  而且會產生空白行——屍檢自己會安靜地失效。
- `tests/test_no_silent_gate.py` 走 AST：任何會吞掉失敗的地方（含
  `contextlib.suppress`）要嘛留痕、要嘛在原始碼上寫下 `# quiet-ok: 理由`。
  檔案清單**掃目錄**而不是寫死三個名字，並涵蓋 `scripts/release.py`。
- `.gate_fail` 現在**有人讀**：它在 `verify_gate` 裡躺了兩個月，全 repo 沒有
  任何東西打開過它。SessionStart 會把筆數與最近幾行送進上下文。
- 測試一律跑 gate 的**副本**。原本測試驅動生產檔，於是刻意注入的失敗累積進
  產品自己的遙測——實測一次全套寫 27 行，全部是雜訊、零筆真實失效，而
  SessionStart 會照實喊「⚠ 閘曾經靜默失效（27 筆）」。假警報會訓練讀者忽略它，
  等於把整個機制廢掉。現在一次全套寫 0 行。

⚠ 這個機制的守衛自己被抓出四類假綠，全部由「不是我選的突變」逼出來，也全部
記在那個檔案的 docstring 裡：Q4 走不到它宣稱驗的那段程式；**Q7** 在「遙測整個
死掉」時照樣綠（那是「永遠是 0」型的假綠，已補陽性對照）；
Q1 的判定漏掉 `contextlib.suppress`（含別名）、把條件式 `raise` 算成往上丟、
把巢狀呼叫算成外層有留痕、看不見 `finally: return`，而且檔案清單寫死。
⚠ 條件式那一條修過兩次：第一次只擋住 `if cond: raise`，它的**鏡像**
（`if isinstance(exc, OSError): return` 之後才 `raise`）照樣全綠。
⚠ Q6 是上一個 commit 修的，不是這一批——當時的 commit 訊息把它算進來了。

⚠ 它只掃**例外處理**。「不是 except 的安靜早退」（`if not root: return 0` 這類）
仍然只有個別情境測試在守——包括 CHANGELOG 已記的那條已知限制（`cd` 到別的 repo
時接線閘檢查錯對象，4.9%），它翻轉判定而不留任何痕跡。

### Known limitations

- **目標閘會對「突變測試」開火**，而本套件的協議自己規定突變測試是唯一的驗收。
  突變測試的節奏是「把程式改壞 → 跑同一條測試 → 紅 → 還原 → 再跑」，在閘看來
  就是同一個鍵連續失敗，第 2 次就擋。2026-09-06 開發本版時**實際擋到作者三次**。
  沒有修：閘沒有辦法從指令本身看出「這次紅燈是刻意的」，而任何「宣告豁免」的
  機制都是再開一個會被濫用的面（這一天已經證明過兩次）。代價是一個回合——它是
  軟擋，再結束一次就放行。解鎖條件＝找到一個不需要新豁免面的判別方式。

- **驗證閘的誤擋率目前量不到。** 接線閘的真相可以問 git（守衛有沒有跑），目標閘
  可以拿真實 transcript 的紅綠回放，而驗證閘的真相是「這一輪算不算跑過測試」
  ——那正是它自己的 `TEST_CMD_RE` 在判的事，用它當判準會變成循環論證。
  ⚠ 我一度用「工具輸出裡有沒有 `N passed`／`N failed`」當獨立判準，量出「1.5 比
  1.4.3 多兩條誤擋」。**那個結論是錯的**：那兩條命中的是應用程式的統計輸出
  （`failed=201`、`rows=0 failed=0`），不是測試摘要；而 1.4.3 之所以「零誤擋」，
  是因為它的回合判定是反的、幾乎什麼都看不見。兩個錯誤疊起來長出一個假的退步。
  解鎖條件＝找到一個與指令辨識無關的「這一輪跑過測試」判準。

- **量測後刻意不修的三項**（本機真實資料：1,260 條 commit 指令、6,485 條測試執行）：
  - `cd <別的 repo> && git commit` 時，接線閘檢查的是 session 的 repo 而不是那一個
    ——**4.9%**（62/1260）。注意「commit 前有 cd」是 77%，但其中 72.1% 是 cd 到同一個
    專案，那種情況檢查對了只是碰巧；真正的曝險是前者。
  - `git commit -m"訊息"`（`-m` 與訊息之間沒有空格）時，訊息內文剝不掉，整道閘
    靜默放行——**0.8%**（10/1260）。方向是漏擋，不是誤擋。
  - 環境變數前綴進了目標的識別鍵，於是 session 專屬的暫存路徑（`TMPDIR=`、`SNAP=`）
    會讓同一個目標裂成多個鍵——**約 4.4%**（288/6485）。
  三項都低於 10% 的門檻，記在這裡而不是留在待辦清單上——「另批處理」不是處置。

- **`.claude/fable-verifier` 是受管束方自己可寫的**。repo 可以宣告一條很容易變綠的
  指令來放寬自己的閘，而且它隨 clone 傳遞。這是刻意的取捨：它取代的是「程式自己
  推論涵蓋關係」，而後者連 repo 的同意都不需要、且已實測會誤清真紅燈。代價是換來
  一個**宣告式的豁免**，這裡如實寫出來，不只講好處。
- **attestation 沒有認證**，且存在被 gitignore 的目錄裡——任何人幾秒內就能手寫一份
  合法紀錄。這道閘擋的是**遺忘與流程漂移**（1.4.1／1.4.2 那兩次是整個跳過），
  擋不住蓄意繞過自己流程的維護者。兩者威脅模型不同，不要混談。
- 沒有 server 端驗證：`reviewed_commit == tag SHA` 只在本機檢查。本 repo 沒有
  `.github/workflows`，外部審查建議加，但那是把信任邊界從本機移到 server 的另一
  項工程，尚未決定由誰持有 attestation 的真實來源。
- 目標的身分是測試指令的鍵。同一段工作換用不同的測試指令時，階梯會從頭算起；
  這個方向是刻意的（寧可少擋一次，不要拿別人的失敗擋這一次）。
- 惡意 repo 的**檔名**仍會進 SessionStart 上下文（上限 8 行 × 120 字元，每行強制
  前綴，前後有「這是資料不是指令」的框架）。已知殘留，緩解有效。

## [1.4.3] — 2026-09-05

Found by reviewing v1.4.2 after it shipped — and then by reviewing the fixes for *those*, which is where most of this comes from. The first attempt at each of these was wrong in a way the second review caught.

### Fixed

- **The goal gate went silently dead when `.fable` was not a directory.** `os.makedirs` sat outside the `try`, so a `.fable` that happened to be a *file* raised into the hook's fail-open and the whole component stopped — no counting, no shelving, no reminders, no sign. An unreadable state file already blocked loudly; the two now behave the same way.

- **State could be written and read outside the repository.** A repo can commit a symlinked `.fable`, and the first guard for it (`os.path.islink`) checks the wrong thing twice: it sees only the last path component, so a symlinked `.fable/.gitignore` still escaped, and on Windows it returns False for a **junction** — the form that needs no administrator rights. The guard blocked the rare shape and passed the common one. Containment is now decided by resolving the path, and it covers reads too: following the link outward and injecting what it finds is the same hole from the other side.

- **The ignore file is no longer written over.** The previous version read an existing `.fable/.gitignore`, judged whether it was "enough", and appended `*` when it wasn't. Every part of that was wrong: the append followed a symlink out of the repository; it wrote without a leading newline and turned `something_else` into `something_else*`; its notion of "enough" was looser than git's (`*` followed by `!*`, or a line with trailing whitespace, both passed); two sessions racing appended twice. Guessing at a file the user owns kept producing new ways to damage it, so it no longer guesses — the ignore file is written only when the gate creates the directory itself.

- **A shelved item's `note` is truncated before it is injected.** `last_command` was capped at 160 characters and `note` was not, while both come from a file a repository can commit.

### Known limitations

- Two sessions shelving in the same repo at the same time can lose an entry: the state is a read-modify-write with no lock (measured: 5 of 5). Recorded in `tests/test_goal_gate.py`.
- A `goal_state.json` the user has already committed cannot be un-tracked by an ignore file. Writes to it then show up in `git status`, which is visible rather than silent.

## [1.4.2] — 2026-09-05

1.4.1 was published without the review that 1.4.0 had just made mandatory. Running it afterwards found that 1.4.1 had fixed one instance of a class and left the class alive — plus two regressions of its own.

### Fixed

- **The whole gate was off in any repository whose path contains non-ASCII characters, on the platform this kit targets.** `subprocess.run(..., text=True)` decodes git's UTF-8 output with the *locale* encoding; on a factory zh-TW / ja / ko Windows (`PYTHONUTF8=0`, cp950) that raises inside subprocess's reader thread, `stdout` comes back `None`, `.strip()` raises `AttributeError`, and the hook's fail-open swallows it. Measured: `git commit --no-verify` in an opted-in repo under a Chinese path was **not blocked**, and a traceback went to stderr. All four subprocess calls in the two hooks now decode as UTF-8 explicitly.

  1.4.1 changed how the *file name* was computed and never touched the decode boundary one layer earlier — the same class, one step up. The test that guarded 1.4.1's fix inherited the author's `PYTHONUTF8=1`, so it proved the author's environment rather than the fix; it now runs with the platform default.

- **`cut -c1-120` truncates bytes, not characters** (GNU coreutils), so a CJK file name could be cut mid-character and put a broken UTF-8 sequence into the session context. The fix for "bytes versus characters" had committed the same error one line later. Truncation moved to the writing side, where it counts characters.

- **`git ls-files` escapes non-ASCII names into octal** (`"tests/test_\346\270\254…"`), which made the hint unreadable for exactly the readers it was meant for. Now uses `-z`.

- **`python3 … || python …` in the declaration could turn a red guard green** when the two interpreters differ, and ran the whole suite twice on the red path. Replaced by resolving the interpreter once.

### Changed

- The bounds on the injected hint are now asserted directly — eight entries, 130 characters each, checked on both the note and the injected block — rather than through a "total output under 20 000 characters" threshold that stayed green with the length cap removed.

- Existing Windows clones need `git add --renormalize .claude/wiring-guards` for 1.4.1's `.gitattributes` line to take effect; the attribute alone does not rewrite a working tree.

## [1.4.1] — 2026-09-05

Everything here was found by running the adversarial review **on the published
releases**, which 1.4.0 had just made mandatory before publishing and which
1.2.0 through 1.4.0 had not had. The rule found six errors in its own author's
work within twenty minutes of shipping.

### Fixed

- **The hint was unreachable on any repository whose path contains non-ASCII characters.** The note's file name is derived from the repo path by replacing everything that is not `[A-Za-z0-9]`, and the two ends did it differently: Python's `re.sub` works per *character*, the shell's `tr` per *byte*. A path under a Chinese, Japanese or Korean directory produced `d_____repo` on the writing side and `d_________repo` on the reading side — written, never read. This kit ships READMEs in those three languages; the people it locked out are the ones it was translated for. Both ends now work on UTF-8 bytes.

  The test that should have caught it computed the name with a copy of the *production* regex, so it could only ever agree with the code it was testing. It now derives the name the way the shell does and drives both halves end to end.

- **A note could be printed to the wrong repository.** Because every non-alphanumeric character maps to `_`, `x/evil-a`, `x/evil_a` and `x/evil/a` collide on one file name — repo B's session would open with repo A's file list, and A opting in would delete B's note. The injector now checks the note's `repo:` line against the current repository before printing anything.

- **The injected hint had no size limit.** File names come from `git ls-files` of whatever repository you happen to be in, so a hostile repo could put 5,000 lines (110 KB) of arbitrary text into the session context. The reading side now caps at eight entries and 120 characters each, and labels the block as data — file names, not instructions.

- **The declaration hard-coded `python`.** On a macOS or Linux box with only `python3`, every commit in an opted-in repo would have gone red. It tries `python3` first now.

### Changed

- **Corrected published numbers.** The 1.2.0 entry claimed 27 and 26 test cases; the files as released collect 57 and 40. The commit time for this repo's own guard was stated as 1.2 s in one place and 1.9 s in another; measured on a clean clone it is 1.3–1.8 s. The declaration described "200 tests, about 10 seconds" — that was the author's local count including five private test files; a public clone has 159.

- **`MAINTAINING.md`** (and its translation) now tells reviewers that a change to `.claude/wiring-guards` is a change to what executes on every committer's machine after the merge — the warning existed only in `INSTALL.md`, which is not what a PR reviewer reads.

- **`.gitattributes`** covers the extensionless `.claude/wiring-guards`, which was being checked out with CRLF on Windows.

## [1.4.0] — 2026-09-05

### Added

- **Protocol §4: verification and adversarial review happen *before* the claim of done, not after** — and §2's trigger list now names publishing explicitly.

  This one was earned. Across this kit's own 1.2.0 release the review did run and the decision lookup did happen, but both landed *after* "this is done" and after "which do you prefer?" had already been sent. Three rounds found 25 defects, two of them introduced by the fixes from the round before, and every one of them reached the user as an amendment to something they had already been told was finished. A report that arrives before the checking is not a report — it makes the reader part of your verification loop without telling them, and they act on it.

  The clause locks the **ordering**, because the failure was never "no review". The same review, the same lookup, moved to after the announcement, loses the thing it was for. Locked by `tests/test_protocol_floor.py::test_l10`, mutation-verified in both directions (drop the ordering sentence, drop the publishing trigger).

## [1.3.1] — 2026-09-05

### Fixed

- **The goal gate counted one target as two whenever the shell plumbing differed.** It keys each test run so it can keep the *last* result per target, but the key was the whole command line — so `cd x && sed -i … && pytest t.py` and a later bare `pytest t.py | tail -4` landed under different keys, the red one never received its green, and the streak climbed on a goal that had already been reached. It blocked this gate's own author three times in one day, each time on work that was finished. The key is now the test invocation itself: the pipeline or redirection you view it through and the `cd`/`sed` you reached it with are not part of it. The shelf entry still records the command as it was actually typed — the key exists to recognise a target, not to describe it.

### Changed

- **This repo now opts itself into its own wiring gate.** Up to 1.3.0 the gate guarded other people's repositories and not the one that ships it — which is the failure it exists to catch. `.claude/wiring-guards` lists the two general guards (every hook must appear in the health check's list; INSTALL step 5's table must match that list) and runs in about 1.5 seconds on commit. The full suite stays a pre-push responsibility; this gate only promises that the wiring class cannot slip through.

## [1.3.0] — 2026-09-05

### Added

- **The wiring gate now finds the repos nobody opted in.** Opt-in has a failure mode that mirrors the one the gate exists for: it does nothing, forever, in every repository somebody meant to enable it in and forgot. When a `git commit` happens in a repo with **no** declaration, the gate now asks `git ls-files` whether that repo already contains guards of the shape it protects — a test file whose name carries both a test word and a wiring word (`test_*_gate.py`, `test_wired_*.ts`, …). If it finds some, it leaves a note; the `SessionStart` hook reads that note and says so once, in the session where you can act on it. Opting the repo in clears the note.

  **It is a note on disk rather than a message from the gate itself, and that is not an implementation detail.** A `PreToolUse` hook has no way to say anything without also blocking: `permissionDecision: "allow"` discards its reason, and stderr on exit 0 is thrown away. An earlier version of this idea did write to stderr — the hint reached nobody while the "already hinted" stamp was written anyway, which is a mechanism that looks like it is protecting you and is not there at all. `SessionStart` output does reach the model, so that is where it goes.

  The scan runs only on a commit command in a repo without a declaration, keys on file names rather than contents, and caps at eight results. Failing to write the note never affects the commit.

## [1.2.0] — 2026-09-05

> **Verified on Windows only**, same as 1.1.0. Both new gates are unit-tested against real files and real transcripts; neither has been exercised on macOS or Linux.

### Added

- **Wiring gate** (component 4, `.claude/hooks/wiring_gate.py` + `wiring_runner.sh`, `PreToolUse` on `Bash|PowerShell`) — a second rung on the same ladder as `verify_gate`. `verify_gate` catches *changed code, no test run*; this catches the next failure along: **the test ran, it passed, and the thing it guards is not on any execution path.**

  That failure is worse than not doing the work at all. Undone work stays on the list; work that shipped gets ticked off, and the gap it was supposed to cover is then unwatched. Four instances surfaced in one repository in a single day (2026-09-05): a rate limiter carrying a `WIRING_TODO` with zero production calls for two months; a script to remove a deprecated scheduled task that never ran once because it lacked a BOM; a maintenance-lease guard covering one of two restart paths; a rebuild primitive with no callers. All four had passed review.

  The gate is **opt-in per repository** and costs one `exists()` check in repos that have not opted in. Where a repo ships `.claude/wiring-guards`, a `git commit` is blocked when the installed pre-commit hook would never run that declaration (`.git/hooks/` is not version controlled, so after a re-clone every guard file is present and none of them execute), and `--no-verify` is refused because it skips the hook without leaving a trace in git history. `ALLOW_UNWIRED=1 git commit ...` states an exception on the record.

  **The two halves enforce differently, and the difference matters.** `wiring_runner.sh` is a git hook: git runs it, so it covers every committer — the agent's Bash tool, its PowerShell tool, a human's terminal, a subagent — and no way of phrasing the command avoids it. The `PreToolUse` half reads a command string before it runs, which is a best-effort reading and cannot be complete: three rounds of adversarial review found it missing multi-line commands, leading global options (`git --no-pager commit`), quoted flags, prefix abbreviations (`--no-veri`) and per-invocation `-C`/`-c`. All of those are fixed and tested, and the ones that remain are structural — a commit reached through `eval`, `sh -c`, `xargs`, `Start-Process` or a git alias is invisible to any string inspection. Treat it as an early warning that saves you a round trip, not as the enforcement.

  `wiring_runner.sh` is the per-repo pre-commit runner. It closes three silent-skip holes found in review, each of which made the runner report **green while skipping guards**: `eval` inheriting the declaration file as stdin (one guard that reads stdin swallowed every remaining line), a final line with no trailing newline (last guard skipped), and a `pytest` invocation exiting 0 having run nothing (bad path, all skipped, over-filtered by `-k`).

- **Goal gate** (component 5, `.claude/hooks/goal_gate.py`, `Stop` + `UserPromptSubmit`) — the rung after that: **it is wired, it runs, and the goal still is not met.**

  The first failure is normal work — find the cause, fix, retest. The second is the interesting one: it means the root cause you named is probably not the root cause, and a third attempt built on the same reading is the same attempt wearing different clothes. So at two consecutive failures the gate blocks once and requires an adversarial review of the root-cause claim before the next attempt. At three it stops the item outright, writes the shelf entry itself, and tells you to move to work that does not depend on it.

  Two design points, both learned the hard way:

  - **The gate writes the shelf entry, the agent does not.** Anything that depends on an agent remembering to record something is the exact failure this ladder exists to remove.
  - **The nag is bounded.** Blocking is triggered by a shelved entry whose `note` is still empty, not by "this turn didn't mention it". The latter fires on every unrelated turn until the shelf is cleared, and a gate that nags gets bypassed. Filling in the note is a one-time act that ends the blocking permanently, which is what makes it enforceable.

  Failure detection keys on **the last test summary line in the output** (`12 passed in 1.2s`, `1 failed, 11 passed`, `3 errors in 0.5s`), not on "did anything fail anywhere in this turn". That earlier reading fired on the two practices this protocol itself mandates, both red-then-green by construction: mutation testing and fail-then-pass evidence. It blocked its own author twice on the day it was written — once on three deliberate mutations of a working guard, and again when a whole break-run-restore-run cycle arrived as **one** shell call with its outputs concatenated, which no per-command keying can split. Where there is no summary line at all — script-style tests that raise and print only a traceback — it falls back to soft markers (`AssertionError`, `FAILED …`), which also occur in passing runs and therefore only decide when nothing better is available. It errs toward "not failed": a false positive fires during normal work, and that is how gates get disabled.

  Thresholds are configurable (`FABLE_GOAL_ADVERSARIAL_AT`, `FABLE_GOAL_SHELVE_AT`) because a suite that takes 3 seconds and one that takes 30 minutes do not deserve the same patience. State lives in `<repo>/.fable/goal_state.json`, now gitignored.

  This counter is about **the goal** and is deliberately a fourth counter, separate from the three already in the governance skills — same method twice (`cognitive-rubrics`), same error twice (same skill), a subagent's first substantively wrong result (`model-dispatch-rules`). Those skills state three times that the counters must not be merged; this one honours that.

- **Protocol §4b** — the behavioural half of the goal ladder, including "when the user comes back, raise the shelved items before resuming anything". §4 also gains the behavioural half of the wiring gate: shipping something that only matters when it is called requires a test asserting **it is on an execution path**. Both are locked by `tests/test_protocol_floor.py` (L7–L9, mutation-verified).

- **tests/test_wiring_gate.py** (57 cases as released) and **tests/test_goal_gate.py** (40), all driving the real hook files and real JSONL transcripts rather than a copy of their logic. Nine mutations verified between them — for the wiring gate: un-stripping commit message bodies (a commit whose *message* mentions `--amend` silently disarmed the whole gate, and the commit that shipped this mechanism was exactly that), removing the wiring check, removing `</dev/null`, removing the trailing-newline handling; for the goal gate: not resetting the streak on green (the counter becomes a ratchet and eventually fires on unrelated work), not writing the shelf entry, not resetting after shelving (the next goal starts already at strike three), nagging on "didn't mention it" instead of the empty note, and dropping the `stop_hook_active` pass-through (which could deadlock a session).

### Fixed

Both gates were put through the kit's own three-opponent review before release — twice, because the first round's fixes turned out to need a review of their own. Sixteen defects between them, each fix shipping with a test and a verified mutation.

The most serious was found in the second round: **a `git commit` on any line but the first was invisible to the wiring gate.** The pattern that recognises the command accepted `;`, `&&` and a pipe as what precedes it, but not a newline — so `git add -A` followed by a newline and `git commit --no-verify` was not examined at all. Multi-line shell is the ordinary way an agent writes a command, which means the gate had been closer to decorative than to enforcing. Continuations (`\` and a backtick before a newline) join their lines before analysis for the same reason.

- **The wiring gate read flags from the whole command line, and short flags only in their unclustered form.** Three consequences, all reproduced: `git commit -nm "x"` was let through (`-nm` *is* `-n -m`); `git commit --amend --no-verify` was let through because `--amend` was tested first and returned early; and `git commit -m "x" && git log -n 1` was **denied** — the `-n` belonged to `git log`. The false deny was the worst of the three: a gate that fires on ordinary work gets switched off. Flags are now read from the `git commit` segment only, clusters are decoded, and `--no-verify` is checked before `--amend`.

- **The wiring gate assembled `<root>/.git/hooks/pre-commit` as a string.** In a worktree or submodule `.git` is a *file*, so that path never exists: every commit in an opted-in repo was denied, and the remedy the denial printed (`cp … .git/hooks/pre-commit`) could not be carried out there. With `core.hooksPath` set (husky, lefthook) the error runs the other way — the path exists while git reads a different one, passing a repo whose guards never run. It now asks git: `git rev-parse --git-path hooks/pre-commit`.

- **The runner reported green when it had run nothing.** An unreadable declaration made the read loop execute zero times and still exit 0; a declaration containing only comments did the same while looking like a gate. Both are red now — the same rule the runner already applied to a pytest run with nothing passed.

- **The goal gate overwrote a state file it could not read.** `load_state` returned an empty state on any error and the next write replaced the whole file, so a truncated or locked `goal_state.json` silently discarded the shelf, including notes written by hand. A missing file is still a fresh start; an unreadable one is now left alone.

- **A run with no tests cleared the streak.** `pytest -k nomatch` prints `no tests ran` and exits 0; counting that as a pass reset the ladder, so a goal that failed, ran something vacuous, then failed again never reached the second rung. A vacuous run is now neither a pass nor a failure.

- **Mentioning a shelved item's id satisfied the shelf gate without writing the note.** Since §4b instructs the agent to raise shelved items when the user returns, the protocol's own instruction was the unlock code, and the note was never written. The empty note is now the only trigger — as this changelog already described it.

- **Every `key=value` in a stored command is masked.** `GITHUB_TOKEN=… pytest` matches the test-command pattern, and the command is both written to a file inside the user's repo and read back into the conversation on the next turn. Masking only the leading assignment left `cd r && TOKEN=… pytest`, `env TOKEN=… pytest` and `pytest --db-url=postgres://u:p@h/db` in the clear. Keys stay visible so the command is still recognisable.

- **The state directory now ignores itself.** `.fable/` holds the user's failing commands and lands in *their* repository; telling them to add it to `.gitignore` (INSTALL step 11) only helps the people who read that step, and a repo without a `.gitignore` would have committed it on the next `git add -A`. The directory now carries its own `.gitignore`. The temp file used for atomic writes also carries the process id — two sessions in one repo shared a single `goal_state.json.tmp`.

- **Short flags are decoded as flags, not searched as text.** `-nm` is `-n -m`, but `-Sjohn` is `-S` with a key id that merely contains an `n`, and matching the letter anywhere denied that commit. The scan now walks each token and stops at the first value-taking flag.

- **A one-shot `-c` is honoured when asking git where hooks live.** `git -c core.hooksPath=/dev/null commit` points git at a directory with no pre-commit and leaves no configuration behind; asking `git rev-parse` *without* that same `-c` answered for a different configuration and passed the commit. `git -C <path> commit` likewise acts on `<path>`, not on the session's directory, and the declaration that matters is the one over there.

- **The runner's new red states route through the existing escape.** An unreadable or guard-less declaration made it exit non-zero *before* the `ALLOW_UNWIRED=1` check — and since `--no-verify` is blocked too, that combination left a repository with no way to commit at all. A gate with no exit is a gate people delete.

- **An unreadable state file now says so.** Refusing to overwrite it protects the shelf, but staying silent about it left the whole component doing nothing with no way to find out — precisely the failure this ladder exists to remove.

- **A vacuous run is judged on the same line as everything else.** Reading "no tests ran" from anywhere in the output meant a guard printing `[wiring] no tests ran` before `12 passed` counted as vacuous, so a genuine green stopped clearing the streak. Fail, pass and vacuous are now all decided by the last summary line.

### Changed

- **Health check** (`scripts/fable_doctor.py`) now tracks **(event, script) pairs instead of one script per event** — `goal_gate.py` is registered on two events, and `UserPromptSubmit` now hosts two scripts. Keyed by event alone, the second script on an event is invisible to the doctor: not reported as missing, simply never looked at. Trigger markers are keyed by script for the same reason — otherwise `goal_gate.py` would inherit `prompt_nudge.sh`'s "last ran" timestamp and appear verified on another script's evidence.

- **Health check also reports which clone a hook runs from** (`hook-elsewhere`). Matching on the file name alone called a hook "registered" while the command pointed at a *different* checkout of this kit — the reported version and copied skills then describe one directory while the executing code lives in another, with nothing in the report showing it. That state existed on the author's own machine while this release was being assembled.

- **New general guards** in `tests/test_fable_doctor.py`: `test_d9` — every Claude hook script in `.claude/hooks/` must appear in the doctor's list; `test_d11` — the six rows of INSTALL.md step 5 must match that list exactly, so the document and the health check cannot drift apart when a component is added. Written as a rule rather than an assertion about these two hooks, so the *next* component cannot ship invisible to the health check; `wiring_runner.sh` is excluded because it is a git hook, not a registered Claude hook.

- **The default README is now Traditional Chinese** (`README.md`); the English text moved to `README.en.md`. The language switcher at the top of all five translations points at the new locations, and the badges read 1.2.0.

- **INSTALL.md**: step 5 now registers six entries (five scripts, `goal_gate.py` twice) with an explicit matcher column; new steps 10 and 11 cover the per-repo wiring opt-in and the goal-gate thresholds, each with a way to verify it that does not require waiting for a real failure. Uninstall gains the per-repo leftovers (`.claude/wiring-guards`, `.git/hooks/pre-commit`, `.fable/`) that removing `~/.claude` alone does not clean up.

## [1.1.0] — 2026-08-27

> **Verified on Windows only.** The install flow, the three hooks and the health check were exercised end to end on Windows. macOS and Linux are expected to work — `INSTALL.md` branches its interpreter detection for them — but neither was run. `scripts/fable_doctor.py` is the way to find out on your own machine.

### Added

- **Health check** (`scripts/fable_doctor.py`): reports which interpreter each of the three hooks actually resolves to, when each last fired, whether the copied skill and agents still match the repo, and whether the recorded install version is behind. Every hook command ends with `|| exit 0`, so a missing or wrong interpreter previously produced no error, no log line, and nothing an install could distinguish from success — this is where that becomes visible. Covered by `tests/test_fable_doctor.py` (9 cases).
- **Upgrade section** in `INSTALL.md`: the hooks are referenced by path and update on `git pull`, but the skill and agents are copies and do not. That drift was undocumented and undetectable across three released versions. An install marker (`~/.claude/fable-harness-install.json`) now records the installed version so the doctor can flag it.
- **The two governance docs are now skills** and therefore reach every project. `model_dispatch_rules.md` → `.claude/skills/model-dispatch-rules/SKILL.md`, `cognitive_rubrics.md` → `.claude/skills/cognitive-rubrics/SKILL.md`. Before this they were only reachable through this repo's own `CLAUDE.md` routing table, which is not installed anywhere — so outside this repo they were advertised in the README and unreadable in practice. A personal skill is available across all your projects, and a skill's body loads only when it is used, so the 182 lines cost nothing until the model needs them. `INSTALL.md` step 8 now copies all three skills.
- **Public governance test** (`tests/test_protocol_floor.py`): a portable content lock on the injected protocol floor, so a fresh clone can re-run at least one governance check rather than none.

### Changed

- **Verification gate** (`.claude/hooks/verify_gate.py`): now counts code changed through the shell — `sed -i`, a redirect, `tee` — not only `Edit`/`Write`/`NotebookEdit`. Measured across the 30 most recent real transcripts: Bash was used 6989 times against 813 `Edit`s and 387 `Write`s, and 887 of those shell calls had the shape of a file write, so roughly a third of all code changes were happening where the gate could not see them. It keys on the *write target's* extension, so `grep -n foo src/bar.py > out.txt` reads Python, writes text, and stays out of scope; writes into a temp or scratchpad path are ignored. False-positive rate on the same data: 149 of 7058 commands, 2.1%. Adds T13–T16. `MultiEdit` was considered and rejected on the same measurement — it appears in 4 of 103 transcripts and 0 of the recent 30.
- **Health check** now watches all three skill copies, not only `adversarial-review` — the two governance docs became copy-delivered in this release, which is exactly the drift the doctor exists to catch.
- **Governance skills**: the six remaining clauses that assumed the project already owns test tooling or version control are rewritten so they hold in a project that has neither. The slow-down trigger leads with the general rule (will this run when nobody is watching) instead of a fixed list of tools; acceptance criteria and the report template's evidence field accept any re-runnable verification, not only a test command; out-of-scope recovery names git as the version-controlled path and falls back to the backup the previous step already requires. Locked by `tests/test_skill_delivery.py`, which also locks each skill's frontmatter — a skill's body loads only when its description makes it look relevant, so a blunted description leaves the skill present, the tests green, and the rules never loaded.
- **Install** (`INSTALL.md`): a missing `settings.json` now creates a minimal one instead of aborting — a brand-new machine is the main case this kit is for, and the old rule (written to protect an existing-but-broken file) caught both situations. Step 5 now requires detecting the interpreters before writing any command string, with OS branches and a template, calling out the two traps seen in practice: only `python3` existing, and a bare `bash` on Windows resolving to the WSL launcher rather than Git Bash. Step 9 now verifies all three hooks instead of only `SessionStart`, using the marker files rather than whether the nudge line happens to be visible in a given client.
- **Protocol** (`.claude/hooks/fable_protocol.md` §3): progress is reported with two values, done and not started. "In progress" is no longer a permitted state — a reply is written and sent in one moment, so unless something was actually launched there is nothing running behind it. When there is real background work, the rule asks for a statement of what has already happened plus what follows when it returns.

## [1.0.2] — 2026-07-20

### Fixed

- **verify_gate**: force UTF-8 stdout (`sys.stdout.reconfigure`) so the block JSON — whose reason string opens with "⛔" — survives Windows consoles that default to a legacy codepage (e.g. cp950). Without it `print()` raised `UnicodeEncodeError`, the fail-open handler swallowed it, and the Stop gate silently never blocked. Landed via [#2](https://github.com/Miguok/fable-harness/pull/2) by [@lepus071](https://github.com/lepus071).
- **verify_gate**: the fail-open handler no longer swallows failures silently — before returning it appends one sanitized post-mortem line (exception class + bounded message, never the raw payload) to a gitignored `.gate_fail`, in a nested try so the telemetry can never break fail-open, and bounded to keep the earliest incident lines. A silently-dying gate is now observable — that exact failure mode is what hid the cp950 bug for days. Adds test T12 (fail-then-pass verified). Idea from [@Atistw](https://github.com/Atistw) in [#3](https://github.com/Miguok/fable-harness/pull/3).

### Added

- **Maintainer guide** (`MAINTAINING.md`, + 繁體中文 translation): the PR merge SOP for keeping the contributor list clean — squash-merge and drop the `Co-Authored-By: Claude <noreply@…>` trailer so no phantom contributor appears.

### Changed

- **Docs**: the README "How it works" section (all five languages) now documents the token efficiency that falls out of the architecture — tiered model routing plus context-isolated, parallel sub-agents — noting that no Fable-specific benchmark figure is claimed.

## [1.0.1] — 2026-07-07

### Fixed

- **verify_gate**: `TEST_CMD_RE` now recognizes script self-test entrypoints — a `--test` flag on any command (e.g. `python3 zh_convert_safe.py --test`) counts as a test run, so the Stop gate no longer falsely blocks a turn that ran one. Look-alike flags (`--test-pypi`, `--testing`, `--tests`) stay blocked via a `(\s|$)` anchor. Adds test T11 (allow + block cases, fail-then-pass verified). Reported by [@Jia-Hong-Peng](https://github.com/Jia-Hong-Peng) in [#1](https://github.com/Miguok/fable-harness/pull/1).

## [1.0.0] — 2026-07-07

First tagged release. The kit is feature-complete and globally deployed.

### Included

- **Behavior protocol** injected at session start (`.claude/hooks/fable_protocol.md` + `inject_protocol.sh`), codename `FABLE-PROTOCOL-V1-CANARY`.
- **Per-turn nudge** (`.claude/hooks/prompt_nudge.sh`) and **verification gate** (`.claude/hooks/verify_gate.py`) with native cross-scope de-duplication.
- **Adversarial review** skill (`.claude/skills/adversarial-review/`) and the three opposition agents (`skeptic`, `red-team`, `simplifier`).
- **Model routing** table (`CLAUDE.md`) and **harness detector** (`scripts/detect_harness.py`).
- **Governance docs**: `model_dispatch_rules.md`, `cognitive_rubrics.md`.
- **Docs**: `README.md` and translations (繁體中文 / 简体中文 / 日本語 / 한국어), `INSTALL.md`, MIT `LICENSE` (+ 繁體中文 translation).
