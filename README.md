# Fable Harness

> A drop-in behavior protocol that makes Claude Code (Opus / Sonnet / Haiku) work like a disciplined engineer — look before you leap, say your assumptions out loud, get a second opinion before trusting big conclusions, and prove your work with real tests.

[繁體中文](README.zh-TW.md) &nbsp;·&nbsp; ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## What is it

Fable Harness is a small kit — a few hooks, a skill, and some sub-agents — that gets injected into every Claude Code session automatically. It doesn't teach Claude new tricks. It makes sure Claude *follows a disciplined process* every single time: gather evidence before answering, state assumptions instead of guessing, challenge its own big conclusions before trusting them, and show real proof (not just "looks good to me") that a change actually works.

Think of it as a behavioral floor, not a framework. It doesn't plan your sprints or run your CI pipeline — it just keeps the agent honest, careful, and verifiable while it works.

## Why

This kit is distilled from the second open release of Fable (Anthropic's Fable model) — the careful, disciplined way that model approached tasks. Rather than keep that discipline locked inside one model, this kit extracts it into a reusable protocol and uses it to reinforce the working harness around Opus (and other Claude models), so they operate the same disciplined way, session after session, regardless of which model happens to be driving.

To be upfront about the limits: hooks and skills can only transplant the *procedure* (observe first, state assumptions, cross-examine conclusions, demand verification evidence) — not a model's innate judgment. But in practice, most of the gap between "good" and "sloppy" agent behavior comes from skipped procedure, not missing judgment. That's the gap this kit closes.

## How it works

- **OODA loop** — before answering, Claude gathers evidence (search/read the actual files, never guess from training memory), states its assumptions out loud, turns the task into something verifiable ("make it work" isn't good enough), then makes small changes and checks each one.
- **Multi-party adversarial review** — this kit's signature move. Before trusting a big conclusion (an architecture decision, a root-cause diagnosis, anything that could affect production), Claude dispatches three independent "opposition" sub-agents *in parallel*, each with a different job: a **skeptic** who looks for logical holes, a **red-team** who looks for security and failure risks, and a **simplifier** who looks for needless over-engineering. The conclusion only gets trusted if a majority of the three "survive" the challenge.
- **Model routing** — reasoning, architecture, and root-cause work stays on whichever model is currently driving; coding and refactoring gets routed to Sonnet; batch file work, search, and text cleanup gets routed to Haiku. Right-sized model for the job.
- **Definition of Done** — if a change touches actual logic, it needs an automated test and evidence that the test failed before the fix and passed after. Eyeballing the output or a stray `console.log` doesn't count as verification.
- **Honest reporting** — the first sentence of any report is the actual result (not a lead-up); failures get reported as failures, not softened.

## What's inside

| Piece | File | What it does |
|---|---|---|
| Behavior protocol | `.claude/hooks/fable_protocol.md` + `inject_protocol.sh` | Injected at the start of every session |
| Per-turn nudge | `.claude/hooks/prompt_nudge.sh` | A one-line reminder injected on every user message |
| Verification gate | `.claude/hooks/verify_gate.py` | Blocks the agent from ending a turn where it changed code but never ran a test (once — a second attempt is allowed through) |
| Adversarial review | `.claude/skills/adversarial-review/` | The skill that defines the three-opponent review flow above |
| Opposition agents | `.claude/agents/{skeptic,red-team,simplifier}.md` | The three independent sub-agent personas used in adversarial review |
| Model routing | `CLAUDE.md` | The routing table described above |
| Harness detector | `scripts/detect_harness.py` | Read-only check for whether the project already has its own dev harness (e.g. harnessmith, Superpowers) so Fable knows to step back and just hold the floor |
| Governance docs | `model_dispatch_rules.md`, `cognitive_rubrics.md` | Sub-agent dispatch templates and when-to-slow-down rules |

## Quick start

Clone this repo, then just tell your Claude Code: **"Install Fable Harness by following INSTALL.md."** Claude will read the guide and do the install itself, safely (backup first, never overwrite your existing settings). See [INSTALL.md](INSTALL.md) for exactly what that involves.

## License

MIT — see [LICENSE](LICENSE).
