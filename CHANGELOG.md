# Changelog

All notable changes to Fable Harness are recorded here.

This kit follows [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`:

- **MAJOR** — a breaking change to the protocol contract (a hook/skill/agent removed or renamed, or an incompatible change to how the protocol is injected or how agents are dispatched) that would require users to re-install or change their setup.
- **MINOR** — a backward-compatible addition (a new hook, skill, agent, or governance rule) that existing installs keep working alongside.
- **PATCH** — a backward-compatible fix or wording change (a bug fix in a hook, a clarified rule, a typo).

The current version is also kept in [VERSION](VERSION).

## [Unreleased]

## [1.3.1] — 2026-09-05

### Fixed

- **The goal gate counted one target as two whenever the shell plumbing differed.** It keys each test run so it can keep the *last* result per target, but the key was the whole command line — so `cd x && sed -i … && pytest t.py` and a later bare `pytest t.py | tail -4` landed under different keys, the red one never received its green, and the streak climbed on a goal that had already been reached. It blocked this gate's own author three times in one day, each time on work that was finished. The key is now the test invocation itself: the pipeline or redirection you view it through and the `cd`/`sed` you reached it with are not part of it. The shelf entry still records the command as it was actually typed — the key exists to recognise a target, not to describe it.

### Changed

- **This repo now opts itself into its own wiring gate.** Up to 1.3.0 the gate guarded other people's repositories and not the one that ships it — which is the failure it exists to catch. `.claude/wiring-guards` lists the two general guards (every hook must appear in the health check's list; INSTALL step 5's table must match that list) and runs in about 1.2 seconds on commit. The full suite stays a pre-push responsibility; this gate only promises that the wiring class cannot slip through.

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

- **tests/test_wiring_gate.py** (27 cases) and **tests/test_goal_gate.py** (26 cases), all driving the real hook files and real JSONL transcripts rather than a copy of their logic. Nine mutations verified between them — for the wiring gate: un-stripping commit message bodies (a commit whose *message* mentions `--amend` silently disarmed the whole gate, and the commit that shipped this mechanism was exactly that), removing the wiring check, removing `</dev/null`, removing the trailing-newline handling; for the goal gate: not resetting the streak on green (the counter becomes a ratchet and eventually fires on unrelated work), not writing the shelf entry, not resetting after shelving (the next goal starts already at strike three), nagging on "didn't mention it" instead of the empty note, and dropping the `stop_hook_active` pass-through (which could deadlock a session).

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
