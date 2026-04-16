#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Finding:
    severity: str
    category: str
    path: str
    line_no: int
    message: str
    snippet: str


BLOCK_RULES = [
    ("shell_pipe_exec", re.compile(r"\b(?:curl|wget)\b[^\n|]{0,200}\|\s*(?:bash|sh)\b", re.I), "Pipe-to-shell command added"),
    ("sudo_usage", re.compile(r"\bsudo\b"), "sudo invocation added"),
    ("workflow_write_all", re.compile(r"\bpermissions\s*:\s*write-all\b", re.I), "Workflow requests write-all permissions"),
    ("gh_token_exfil", re.compile(r"\b(?:gh|curl|wget)\b[^\n]{0,200}(?:GITHUB_TOKEN|secrets\.[A-Z0-9_]+)", re.I), "Possible token-bearing network command added"),
]

WARN_RULES = [
    ("package_install", re.compile(r"\b(?:npm\s+install|npm\s+i\b|pnpm\s+add\b|pnpm\s+install\b|yarn\s+add\b|pip(?:3)?\s+install\b|uv\s+pip\s+install\b|cargo\s+install\b|go\s+install\b|brew\s+install\b|apt(?:-get)?\s+install\b)"), "Package install command added"),
    ("dynamic_exec", re.compile(r"\b(?:eval\s*\(|exec\s*\(|os\.system\s*\(|subprocess\.(?:run|Popen|call|check_output)\s*\(|child_process\.|Runtime\.getRuntime\(|ProcessBuilder\()"), "Dynamic execution surface added"),
    ("network_code", re.compile(r"\b(?:requests\.|urllib\.|fetch\s*\(|XMLHttpRequest|httpx\.|aiohttp\.|socket\.|net\.|open\(['\"]https?://|urlopen\s*\()"), "Network call surface added"),
    ("inline_script", re.compile(r"<script\b|innerHTML\s*=|dangerouslySetInnerHTML|json\.dumps\s*\(|JSON\.stringify\s*\("), "Inline script or raw embedding pattern added"),
    ("reviewer_instruction", re.compile(r"ignore previous instructions|run this command|paste this into (?:your )?terminal|execute the following", re.I), "Reviewer-instruction style text added"),
    ("workflow_write_perm", re.compile(r"\bpermissions\s*:\s*[\s\S]{0,80}\b(?:contents|actions|checks|deployments|id-token|packages|pull-requests|security-events)\s*:\s*write\b", re.I), "Workflow requests write permission"),
]

INFO_RULES = [
    ("generated_html", re.compile(r"<html\b|<!DOCTYPE html>", re.I), "HTML artifact changed"),
]


EXCLUDED_PATH_PATTERNS = [
    re.compile(r"^\.git/"),
]

MARKDOWN_SUFFIXES = {".md", ".txt", ".rst"}


def run(cmd, cwd=None):
    return subprocess.check_output(cmd, cwd=cwd, text=True)


def changed_files(base, head):
    out = run(["git", "diff", "--name-only", f"{base}...{head}"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def iter_added_lines(base, head, path):
    diff = run(["git", "diff", "--unified=0", "--no-color", f"{base}...{head}", "--", path])
    new_line = None
    for raw in diff.splitlines():
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", raw)
            new_line = int(m.group(1)) if m else None
            continue
        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith("+"):
            if new_line is None:
                continue
            yield new_line, raw[1:]
            new_line += 1
        elif raw.startswith("-"):
            continue
        else:
            if new_line is not None:
                new_line += 1


def path_excluded(path):
    return any(p.search(path) for p in EXCLUDED_PATH_PATTERNS)


def severity_for_path(severity, path):
    suffix = Path(path).suffix.lower()
    if suffix in MARKDOWN_SUFFIXES:
        return {"block": "warn", "warn": "info", "info": "info"}[severity]
    return severity


def meta_rule_definition(path, line):
    if not path.endswith("scripts/pr_safety_lint.py"):
        return False
    return "re.compile(" in line or "subprocess.check_output(" in line


def markdown_example_line(path, line):
    suffix = Path(path).suffix.lower()
    if suffix not in MARKDOWN_SUFFIXES:
        return False
    stripped = line.strip()
    return stripped.startswith("- ") and "`" in stripped


def scan(base, head):
    findings = []
    files = changed_files(base, head)
    for path in files:
        if path_excluded(path):
            continue
        for line_no, line in iter_added_lines(base, head, path):
            if meta_rule_definition(path, line):
                continue
            rules = []
            if not markdown_example_line(path, line):
                rules.extend(("block",) + rule for rule in BLOCK_RULES)
                rules.extend(("warn",) + rule for rule in WARN_RULES)
            rules.extend(("info",) + rule for rule in INFO_RULES)
            for severity, category, pattern, message in rules:
                if pattern.search(line):
                    findings.append(Finding(severity_for_path(severity, path), category, path, line_no, message, line.strip()))
    return files, findings


def summarize(files, findings):
    by_sev = {"block": [], "warn": [], "info": []}
    for f in findings:
        by_sev[f.severity].append(f)

    lines = []
    lines.append("# PR safety lint")
    lines.append("")
    lines.append(f"Changed files scanned: {len(files)}")
    lines.append(f"Findings: {len(by_sev['block'])} block, {len(by_sev['warn'])} warn, {len(by_sev['info'])} info")
    lines.append("")
    for severity in ["block", "warn", "info"]:
        if not by_sev[severity]:
            continue
        lines.append(f"## {severity.upper()}")
        for f in by_sev[severity]:
            lines.append(f"- `{f.path}:{f.line_no}` [{f.category}] {f.message}")
            lines.append(f"  - `{f.snippet[:180]}`")
        lines.append("")
    return "\n".join(lines), by_sev


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()

    files, findings = scan(args.base, args.head)
    summary, by_sev = summarize(files, findings)
    print(summary)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        Path(step_summary).write_text(summary + "\n", encoding="utf-8")

    for sev in ["block", "warn"]:
        for f in by_sev[sev]:
            level = "error" if sev == "block" else "warning"
            print(f"::{level} file={f.path},line={f.line_no},title={f.category}::{f.message}: {f.snippet}")

    if by_sev["block"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
