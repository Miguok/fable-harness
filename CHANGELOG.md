# Changelog

All notable changes to Fable Harness are recorded here.

This kit follows [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`:

- **MAJOR** — a breaking change to the protocol contract (a hook/skill/agent removed or renamed, or an incompatible change to how the protocol is injected or how agents are dispatched) that would require users to re-install or change their setup.
- **MINOR** — a backward-compatible addition (a new hook, skill, agent, or governance rule) that existing installs keep working alongside.
- **PATCH** — a backward-compatible fix or wording change (a bug fix in a hook, a clarified rule, a typo).

The current version is also kept in [VERSION](VERSION).

## [Unreleased]

### Added

- **Health check** (`scripts/fable_doctor.py`): reports which interpreter each of the three hooks actually resolves to, when each last fired, whether the copied skill and agents still match the repo, and whether the recorded install version is behind. Every hook command ends with `|| exit 0`, so a missing or wrong interpreter previously produced no error, no log line, and nothing an install could distinguish from success — this is where that becomes visible. Covered by `tests/test_fable_doctor.py` (9 cases).
- **Upgrade section** in `INSTALL.md`: the hooks are referenced by path and update on `git pull`, but the skill and agents are copies and do not. That drift was undocumented and undetectable across three released versions. An install marker (`~/.claude/fable-harness-install.json`) now records the installed version so the doctor can flag it.
- **Public governance test** (`tests/test_protocol_floor.py`): a portable content lock on the injected protocol floor, so a fresh clone can re-run at least one governance check rather than none.

### Changed

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
