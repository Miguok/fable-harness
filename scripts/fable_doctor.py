#!/usr/bin/env python3
"""Fable Harness health check — reports the failure modes an install can hide.

Three hooks are registered by absolute path and each one ends with ``|| exit 0``.
That keeps a broken hook from wedging a session, but it also makes "the interpreter
does not exist" look exactly like "the hook ran fine". Nothing is printed and nothing
is logged. This script is the place where that becomes visible.

It also compares the *copied* artifacts (skill, agents) against the repo. The hooks
update themselves on ``git pull`` because they are referenced by path; the copies do
not. Without this check, an upgraded install silently keeps running the old skill.

Usage:
    python scripts/fable_doctor.py --home ~ --repo /path/to/fable-harness
    python scripts/fable_doctor.py --home ~ --repo . --json

Exit code: 0 when no problems were found, 1 when at least one was.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import shutil
import sys
from pathlib import Path

HOOK_SCRIPTS = {
    "SessionStart": "inject_protocol.sh",
    "UserPromptSubmit": "prompt_nudge.sh",
    "Stop": "verify_gate.py",
}

# Only these two hooks write a trigger marker; verify_gate.py does not.
HOOK_MARKERS = {
    "SessionStart": ".last_sessionstart",
    "UserPromptSubmit": ".last_promptsubmit",
}

COPIED_ARTIFACTS = [
    Path(".claude/skills/adversarial-review/SKILL.md"),
    Path(".claude/skills/cognitive-rubrics/SKILL.md"),
    Path(".claude/skills/model-dispatch-rules/SKILL.md"),
    Path(".claude/agents/skeptic.md"),
    Path(".claude/agents/red-team.md"),
    Path(".claude/agents/simplifier.md"),
]

INSTALL_MARKER = "fable-harness-install.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _interpreter_of(command: str) -> str | None:
    """Return the first token of a hook command — the interpreter it will actually use."""
    try:
        tokens = shlex.split(command, posix=False)
    except ValueError:
        return None
    if not tokens:
        return None
    return tokens[0].strip('"')


def _resolves(interpreter: str) -> bool:
    candidate = Path(interpreter)
    if candidate.is_absolute():
        return candidate.exists()
    return shutil.which(interpreter) is not None


def _find_hook_command(settings: dict, event: str, script_name: str) -> str | None:
    """Find the registered command for one event that points at this repo's script."""
    for group in settings.get("hooks", {}).get(event, []):
        for entry in group.get("hooks", []):
            command = entry.get("command", "")
            if script_name in command:
                return command
    return None


def check(home: Path, repo: Path) -> dict:
    """Run every check and return a report dict with a ``problems`` list."""
    problems: list[dict] = []
    hooks_report: list[dict] = []
    claude = home / ".claude"

    settings_path = claude / "settings.json"
    settings: dict = {}
    if not settings_path.exists():
        problems.append(
            {"code": "settings-missing", "detail": f"{settings_path} does not exist"}
        )
    else:
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            problems.append(
                {"code": "settings-unparsable", "detail": f"{settings_path}: {exc}"}
            )

    hooks_dir = repo / ".claude" / "hooks"
    for event, script_name in HOOK_SCRIPTS.items():
        command = _find_hook_command(settings, event, script_name)
        row = {"event": event, "script": script_name, "command": command}
        if command is None:
            problems.append(
                {"code": "hook-missing", "detail": f"{event} is not registered for {script_name}"}
            )
            hooks_report.append(row)
            continue

        interpreter = _interpreter_of(command)
        row["interpreter"] = interpreter
        if interpreter is None or not _resolves(interpreter):
            problems.append(
                {
                    "code": "interpreter-unresolved",
                    "detail": f"{event}: cannot resolve interpreter {interpreter!r} — "
                    "this hook is silently doing nothing",
                }
            )

        marker_name = HOOK_MARKERS.get(event)
        if marker_name:
            marker = hooks_dir / marker_name
            if not marker.exists():
                problems.append(
                    {
                        "code": "never-ran",
                        "detail": f"{event}: no trigger marker at {marker} — "
                        "this hook has never fired",
                    }
                )
            else:
                row["last_ran"] = marker.read_text(encoding="utf-8").strip()
        hooks_report.append(row)

    for relative in COPIED_ARTIFACTS:
        source = repo / relative
        installed = claude / Path(*relative.parts[1:])  # drop the leading ".claude"
        if not source.exists():
            problems.append({"code": "repo-file-missing", "detail": str(source)})
            continue
        if not installed.exists():
            problems.append({"code": "copy-missing", "detail": str(installed)})
            continue
        if _sha256(source) != _sha256(installed):
            problems.append(
                {
                    "code": "copy-drift",
                    "detail": f"{installed} differs from {source} — "
                    "copied artifacts do not update on git pull",
                }
            )

    version_path = repo / "VERSION"
    repo_version = version_path.read_text(encoding="utf-8").strip() if version_path.exists() else None
    marker_path = claude / INSTALL_MARKER
    if not marker_path.exists():
        problems.append(
            {
                "code": "install-marker-missing",
                "detail": f"{marker_path} does not exist — the installed version is unknown",
            }
        )
    else:
        try:
            install_marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            problems.append({"code": "install-marker-unparsable", "detail": str(exc)})
        else:
            installed_version = str(install_marker.get("version", "")).strip()
            if repo_version and installed_version != repo_version:
                problems.append(
                    {
                        "code": "version-stale",
                        "detail": f"installed {installed_version!r} but repo is {repo_version!r} — "
                        "re-run the copy step in INSTALL.md",
                    }
                )

    return {"repo_version": repo_version, "hooks": hooks_report, "problems": problems}


def _render(report: dict) -> str:
    lines = [f"Fable Harness doctor — repo version {report.get('repo_version') or 'unknown'}", ""]
    for row in report["hooks"]:
        state = "not registered" if row.get("command") is None else row.get("interpreter", "?")
        # Only two hooks write a marker. Saying "never" for the third would report
        # "we do not track this" as "this never fired" — the exact confusion this tool exists to remove.
        if row["event"] not in HOOK_MARKERS:
            last = "not tracked"
        else:
            last = row.get("last_ran", "never")
        lines.append(f"  {row['event']:<18} interpreter={state}  last ran={last}")
    lines.append("")
    if not report["problems"]:
        lines.append("No problems found.")
    else:
        lines.append(f"{len(report['problems'])} problem(s):")
        lines.extend(f"  [{p['code']}] {p['detail']}" for p in report["problems"])
    return "\n".join(lines)


def main() -> int:
    """Parse arguments, run the checks, print the report, and return the exit code."""
    parser = argparse.ArgumentParser(description="Check that a Fable Harness install actually works.")
    parser.add_argument("--home", required=True, help="the user's home directory (the one holding .claude)")
    parser.add_argument("--repo", required=True, help="path to the cloned fable-harness repo")
    parser.add_argument("--json", action="store_true", help="emit the raw report as JSON")
    args = parser.parse_args()

    report = check(Path(args.home).expanduser(), Path(args.repo).expanduser())
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_render(report))
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
