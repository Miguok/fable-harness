# Changelog

All notable changes to Fable Harness are recorded here.

This kit follows [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`:

- **MAJOR** — a breaking change to the protocol contract (a hook/skill/agent removed or renamed, or an incompatible change to how the protocol is injected or how agents are dispatched) that would require users to re-install or change their setup.
- **MINOR** — a backward-compatible addition (a new hook, skill, agent, or governance rule) that existing installs keep working alongside.
- **PATCH** — a backward-compatible fix or wording change (a bug fix in a hook, a clarified rule, a typo).

The current version is also kept in [VERSION](VERSION).

## [1.0.0] — 2026-07-07

First tagged release. The kit is feature-complete and globally deployed.

### Included

- **Behavior protocol** injected at session start (`.claude/hooks/fable_protocol.md` + `inject_protocol.sh`), codename `FABLE-PROTOCOL-V1-CANARY`.
- **Per-turn nudge** (`.claude/hooks/prompt_nudge.sh`) and **verification gate** (`.claude/hooks/verify_gate.py`) with native cross-scope de-duplication.
- **Adversarial review** skill (`.claude/skills/adversarial-review/`) and the three opposition agents (`skeptic`, `red-team`, `simplifier`).
- **Model routing** table (`CLAUDE.md`) and **harness detector** (`scripts/detect_harness.py`).
- **Governance docs**: `diagnostics.md`, `model_dispatch_rules.md`, `cognitive_rubrics.md`, `future_session_letter.md`.
- **Docs**: `README.md` and translations (繁體中文 / 简体中文 / 日本語 / 한국어), `INSTALL.md`, MIT `LICENSE` (+ 繁體中文 translation).
