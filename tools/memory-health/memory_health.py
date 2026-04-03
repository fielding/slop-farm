#!/usr/bin/env python3
"""
memory-health: A CLI tool to audit agent memory directories for staleness,
bloat, contradictions, and orphaned files.

Philosophy: Your memory file is not your memory — the retrieval mechanism matters.
An agent can have perfect notes and still lose track of who they are if they
never re-read or reorganize them.
"""

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Try to import rich for colored output; fall back gracefully
try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# ─── Data structures ──────────────────────────────────────────────────────────

SEVERITY_ORDER = {"ok": 0, "warning": 1, "critical": 2}

@dataclass
class Finding:
    severity: str          # "ok" | "warning" | "critical"
    category: str          # e.g. "staleness", "bloat", "orphan", "contradiction", "stale-marker"
    file: str              # relative path of the affected file
    message: str           # human-readable description
    suggestion: str        # actionable advice
    related_file: Optional[str] = None  # for contradiction findings

@dataclass
class HealthReport:
    memory_dir: Path
    index_file: Optional[Path]
    findings: list[Finding] = field(default_factory=list)
    scanned_files: int = 0

    def add(self, finding: Finding):
        self.findings.append(finding)

    @property
    def has_critical(self):
        return any(f.severity == "critical" for f in self.findings)

    @property
    def has_warnings(self):
        return any(f.severity == "warning" for f in self.findings)

    def by_severity(self, severity: str):
        return [f for f in self.findings if f.severity == severity]

    def sorted_findings(self):
        return sorted(self.findings, key=lambda f: -SEVERITY_ORDER.get(f.severity, 0))


# ─── Config ───────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "memory_dir": "memory",
    "index_file": None,          # auto-detected if None
    "max_age_days": 30,
    "max_size_bytes": 51200,     # 50 KB
    "extensions": [".md"],
    "archive_subdir": "archive",
    "review_file": "review-needed.md",
}

def load_config(config_path: Optional[Path], cli_overrides: dict) -> dict:
    cfg = dict(DEFAULT_CONFIG)

    if config_path and config_path.exists():
        with open(config_path) as f:
            file_cfg = json.load(f)
        cfg.update(file_cfg)

    # CLI overrides take highest precedence
    for k, v in cli_overrides.items():
        if v is not None:
            cfg[k] = v

    return cfg


# ─── Scanning utilities ───────────────────────────────────────────────────────

def iter_memory_files(memory_dir: Path, extensions: list[str], archive_subdir: str) -> list[Path]:
    """Return all memory files, excluding the archive subdirectory."""
    archive_path = memory_dir / archive_subdir
    files = []
    for ext in extensions:
        for p in memory_dir.glob(f"*{ext}"):
            if p.is_file() and not p.is_relative_to(archive_path):
                files.append(p)
    return sorted(files)


def file_age_days(path: Path) -> float:
    mtime = path.stat().st_mtime
    age = datetime.now(timezone.utc).timestamp() - mtime
    return age / 86400


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def detect_index_file(memory_dir: Path, extensions: list[str]) -> Optional[Path]:
    """Try common index file locations."""
    candidates = [
        memory_dir / "MEMORY.md",
        memory_dir.parent / "MEMORY.md",
        memory_dir / "INDEX.md",
        memory_dir / "README.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# ─── Checks ───────────────────────────────────────────────────────────────────

def check_staleness(path: Path, memory_dir: Path, max_age_days: int) -> Optional[Finding]:
    age = file_age_days(path)
    rel = path.relative_to(memory_dir)
    if age > max_age_days * 2:
        return Finding(
            severity="critical",
            category="staleness",
            file=str(rel),
            message=f"File is {int(age)} days old (threshold: {max_age_days})",
            suggestion=f"Consider archiving to memory/archive/ or integrating key facts into your index",
        )
    elif age > max_age_days:
        return Finding(
            severity="warning",
            category="staleness",
            file=str(rel),
            message=f"File is {int(age)} days old (threshold: {max_age_days})",
            suggestion=f"Review for relevance; archive if no longer active",
        )
    return None


def check_size(path: Path, memory_dir: Path, max_size_bytes: int) -> Optional[Finding]:
    size = path.stat().st_size
    rel = path.relative_to(memory_dir)
    if size > max_size_bytes * 2:
        return Finding(
            severity="critical",
            category="bloat",
            file=str(rel),
            message=f"File is {size // 1024} KB (threshold: {max_size_bytes // 1024} KB)",
            suggestion="Split into smaller topic files; move historical entries to archive/",
        )
    elif size > max_size_bytes:
        return Finding(
            severity="warning",
            category="bloat",
            file=str(rel),
            message=f"File is {size // 1024} KB (threshold: {max_size_bytes // 1024} KB)",
            suggestion="Consider splitting this file by topic or trimming resolved items",
        )
    return None


def check_orphan(
    path: Path,
    memory_dir: Path,
    index_file: Optional[Path],
    index_text: str,
) -> Optional[Finding]:
    if index_file is None:
        return None
    rel = path.relative_to(memory_dir)
    filename = path.name
    stem = path.stem
    # Check if the index references this file by name or stem
    if filename in index_text or stem in index_text or str(rel) in index_text:
        return None
    return Finding(
        severity="warning",
        category="orphan",
        file=str(rel),
        message=f"Not referenced by index file ({index_file.name})",
        suggestion=f"Add a link or summary to {index_file.name}, or archive if obsolete",
    )


# Patterns for positive and negative claims about a subject word
_POSITIVE_RE = re.compile(
    r"\b(?:always|prefer|use|should|must|is|are|enable|enabled|set to|configured as|"
    r"default is|set|trust|include|keep|run|works with)\s+([a-z][\w\-\.]+)",
    re.IGNORECASE,
)
_NEGATIVE_RE = re.compile(
    r"\b(?:never|avoid|don't|do not|not use|shouldn't|isn't|aren't|disabled|"
    r"exclude|remove|don't use|no longer|deprecated|replaced by|instead of)\s+([a-z][\w\-\.]+)",
    re.IGNORECASE,
)
# Very short tokens are too noisy
_MIN_TOKEN_LEN = 4
_STOPWORDS = {
    "this", "that", "them", "they", "with", "from", "have", "been",
    "will", "your", "more", "some", "also", "when", "than", "then",
    "file", "code", "here", "just", "make", "sure", "need", "want",
    "note", "like", "does", "each", "into", "over", "such", "very",
    "well", "both", "only", "main", "most", "user", "time", "new",
    "all", "any", "one", "two", "the", "and", "for", "but", "can",
    "may", "its", "has", "had", "not", "our", "out", "see", "get",
    "put", "way", "other", "these", "those", "their", "using",
    "added", "adding", "being", "doing", "going", "running", "working",
}

def extract_claims(text: str) -> tuple[set[str], set[str]]:
    """Return (positive_tokens, negative_tokens) from text."""
    pos = {
        m.group(1).lower()
        for m in _POSITIVE_RE.finditer(text)
        if len(m.group(1)) >= _MIN_TOKEN_LEN and m.group(1).lower() not in _STOPWORDS
    }
    neg = {
        m.group(1).lower()
        for m in _NEGATIVE_RE.finditer(text)
        if len(m.group(1)) >= _MIN_TOKEN_LEN and m.group(1).lower() not in _STOPWORDS
    }
    return pos, neg


def check_contradictions(files: list[Path], memory_dir: Path) -> list[Finding]:
    """Compare all pairs of files for potential contradictions."""
    file_claims: dict[Path, tuple[set, set]] = {}
    for p in files:
        text = read_text(p)
        file_claims[p] = extract_claims(text)

    findings = []
    paths = list(file_claims.keys())
    seen_pairs: set[frozenset] = set()

    for i, path_a in enumerate(paths):
        pos_a, neg_a = file_claims[path_a]
        for path_b in paths[i + 1:]:
            pair_key = frozenset([path_a, path_b])
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            pos_b, neg_b = file_claims[path_b]
            # Contradiction: A says "use X" and B says "never X" (or vice versa)
            clash_ab = pos_a & neg_b   # A positive, B negative
            clash_ba = pos_b & neg_a   # B positive, A negative
            clashes = clash_ab | clash_ba

            if clashes:
                rel_a = str(path_a.relative_to(memory_dir))
                rel_b = str(path_b.relative_to(memory_dir))
                sample = sorted(clashes)[:3]
                findings.append(Finding(
                    severity="warning",
                    category="contradiction",
                    file=rel_a,
                    related_file=rel_b,
                    message=f"Potential conflict on: {', '.join(sample)}",
                    suggestion=f"Compare {rel_a} and {rel_b}; reconcile conflicting instructions",
                ))
    return findings


# Date patterns for stale TODO/FIXME markers
_TODO_DATE_RE = re.compile(
    r"(?:TODO|FIXME|HACK|XXX)[^\n]*?(\d{4}[-/]\d{2}[-/]\d{2})",
    re.IGNORECASE,
)

def check_stale_markers(path: Path, memory_dir: Path) -> list[Finding]:
    text = read_text(path)
    rel = str(path.relative_to(memory_dir))
    findings = []
    today = datetime.now(timezone.utc).date()
    for m in _TODO_DATE_RE.finditer(text):
        raw_date = m.group(1).replace("/", "-")
        try:
            marker_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if marker_date < today:
            age = (today - marker_date).days
            findings.append(Finding(
                severity="warning",
                category="stale-marker",
                file=rel,
                message=f"TODO/FIXME references past date {raw_date} ({age} days ago)",
                suggestion="Resolve this item or remove the date marker if still relevant",
            ))
    return findings


# ─── Core scan ────────────────────────────────────────────────────────────────

def scan(cfg: dict) -> HealthReport:
    memory_dir = Path(cfg["memory_dir"]).expanduser().resolve()
    if not memory_dir.is_dir():
        print(f"Error: memory directory not found: {memory_dir}", file=sys.stderr)
        sys.exit(1)

    # Resolve index file
    if cfg["index_file"]:
        index_file = Path(cfg["index_file"]).expanduser().resolve()
    else:
        index_file = detect_index_file(memory_dir, cfg["extensions"])

    index_text = read_text(index_file) if index_file else ""
    report = HealthReport(memory_dir=memory_dir, index_file=index_file)

    files = iter_memory_files(memory_dir, cfg["extensions"], cfg["archive_subdir"])
    report.scanned_files = len(files)

    for path in files:
        f = check_staleness(path, memory_dir, cfg["max_age_days"])
        if f:
            report.add(f)

        f = check_size(path, memory_dir, cfg["max_size_bytes"])
        if f:
            report.add(f)

        f = check_orphan(path, memory_dir, index_file, index_text)
        if f:
            report.add(f)

        for f in check_stale_markers(path, memory_dir):
            report.add(f)

    for f in check_contradictions(files, memory_dir):
        report.add(f)

    return report


# ─── Auto-fix actions ─────────────────────────────────────────────────────────

def apply_fixes(report: HealthReport, cfg: dict, dry_run: bool = False) -> list[str]:
    """
    Perform auto-fix actions:
      - Archive stale/critical files
      - Create review-needed.md for contradictions
      - Append summary reminder lines to index
    Returns a list of action descriptions.
    """
    actions = []
    memory_dir = report.memory_dir
    archive_dir = memory_dir / cfg["archive_subdir"]

    if not dry_run:
        archive_dir.mkdir(exist_ok=True)

    archived: set[str] = set()

    # Archive critically stale or bloated files
    for finding in report.findings:
        if finding.category in ("staleness", "bloat") and finding.severity == "critical":
            src = memory_dir / finding.file
            if not src.exists() or finding.file in archived:
                continue
            dst = archive_dir / src.name
            # Avoid overwriting existing archive
            if dst.exists():
                stem, suffix = src.stem, src.suffix
                dst = archive_dir / f"{stem}-{int(datetime.now().timestamp())}{suffix}"
            actions.append(f"ARCHIVE  {finding.file}  ->  {dst.relative_to(memory_dir)}")
            if not dry_run:
                shutil.move(str(src), str(dst))
            archived.add(finding.file)

    # Create review-needed.md for contradictions
    contradictions = [f for f in report.findings if f.category == "contradiction"]
    if contradictions:
        review_path = memory_dir / cfg["review_file"]
        lines = [
            f"# Review Needed\n",
            f"Generated by memory-health on {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n",
            "The following potential contradictions were detected and require manual review:\n\n",
        ]
        for idx, c in enumerate(contradictions, 1):
            lines.append(f"## {idx}. Conflict in `{c.file}` vs `{c.related_file}`\n")
            lines.append(f"- **Issue:** {c.message}\n")
            lines.append(f"- **Suggestion:** {c.suggestion}\n\n")
        actions.append(f"CREATE   {cfg['review_file']}")
        if not dry_run:
            review_path.write_text("".join(lines), encoding="utf-8")

    # Append orphan reminders to index
    orphans = [f for f in report.findings if f.category == "orphan" and f.file not in archived]
    if orphans and report.index_file and report.index_file.exists():
        lines = [
            f"\n\n<!-- memory-health: unindexed files detected {datetime.now().strftime('%Y-%m-%d')} -->\n"
        ]
        for o in orphans:
            lines.append(f"- [ ] Review unindexed file: `{o.file}`\n")
        actions.append(f"APPEND   orphan reminders to {report.index_file.name}")
        if not dry_run:
            with open(report.index_file, "a", encoding="utf-8") as fh:
                fh.writelines(lines)

    return actions


# ─── Output rendering ─────────────────────────────────────────────────────────

SEVERITY_COLORS = {
    "ok":       "green",
    "warning":  "yellow",
    "critical": "red",
}
SEVERITY_ICONS = {
    "ok":       "ok",
    "warning":  "warn",
    "critical": "crit",
}

def _plain_icon(severity: str) -> str:
    return f"[{SEVERITY_ICONS.get(severity, severity).upper()}]"


def render_plain(report: HealthReport, cfg: dict) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("  MEMORY HEALTH REPORT")
    lines.append(f"  Directory : {report.memory_dir}")
    if report.index_file:
        lines.append(f"  Index     : {report.index_file}")
    else:
        lines.append("  Index     : (none detected)")
    lines.append(f"  Files scanned: {report.scanned_files}")
    lines.append("=" * 70)

    if not report.findings:
        lines.append("\n  All clear. No issues found.\n")
        return "\n".join(lines)

    for sev in ("critical", "warning", "ok"):
        bucket = report.by_severity(sev)
        if not bucket:
            continue
        lines.append(f"\n--- {sev.upper()} ({len(bucket)}) ---")
        for f in bucket:
            icon = _plain_icon(f.severity)
            lines.append(f"\n  {icon} [{f.category}] {f.file}")
            if f.related_file:
                lines.append(f"       vs {f.related_file}")
            lines.append(f"       {f.message}")
            lines.append(f"       -> {f.suggestion}")

    lines.append("\n" + "=" * 70)
    n_crit = len(report.by_severity("critical"))
    n_warn = len(report.by_severity("warning"))
    lines.append(f"  Summary: {n_crit} critical, {n_warn} warning(s)")
    lines.append("=" * 70)
    return "\n".join(lines)


def render_rich(report: HealthReport, cfg: dict) -> None:
    console = Console()

    console.rule("[bold]Memory Health Report[/bold]")
    console.print(f"  [dim]Directory:[/dim] {report.memory_dir}")
    if report.index_file:
        console.print(f"  [dim]Index:    [/dim] {report.index_file}")
    else:
        console.print("  [dim]Index:[/dim] [yellow](none detected)[/yellow]")
    console.print(f"  [dim]Files scanned:[/dim] {report.scanned_files}")
    console.print()

    if not report.findings:
        console.print("[bold green]  All clear. No issues found.[/bold green]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Sev", width=6)
    table.add_column("Category", width=14)
    table.add_column("File(s)", min_width=20)
    table.add_column("Issue", min_width=30)
    table.add_column("Suggestion", min_width=30)

    for f in report.sorted_findings():
        color = SEVERITY_COLORS.get(f.severity, "white")
        sev_text = Text(SEVERITY_ICONS.get(f.severity, f.severity).upper(), style=f"bold {color}")
        cat_text = Text(f.category, style=color)
        file_display = f.file
        if f.related_file:
            file_display += f"\nvs {f.related_file}"
        table.add_row(sev_text, cat_text, file_display, f.message, f.suggestion)

    console.print(table)
    console.print()

    n_crit = len(report.by_severity("critical"))
    n_warn = len(report.by_severity("warning"))
    summary_parts = []
    if n_crit:
        summary_parts.append(f"[bold red]{n_crit} critical[/bold red]")
    if n_warn:
        summary_parts.append(f"[yellow]{n_warn} warning(s)[/yellow]")
    if not summary_parts:
        summary_parts.append("[green]all ok[/green]")
    console.print("  Summary: " + ", ".join(summary_parts))


def render(report: HealthReport, cfg: dict, force_plain: bool = False) -> None:
    if RICH_AVAILABLE and not force_plain:
        render_rich(report, cfg)
    else:
        print(render_plain(report, cfg))


# ─── CLI entry point ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="memory-health",
        description=(
            "Audit an agent memory directory for staleness, bloat, "
            "contradictions, and orphaned files."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  memory-health                          # scan ./memory with defaults
  memory-health --dir ~/agent/memory     # custom directory
  memory-health --max-age 14 --fix       # aggressive 2-week policy, auto-fix
  memory-health --fix --dry-run          # preview fixes without applying them
  memory-health --no-color               # plain text output
  memory-health --config my-config.json  # load config from file
        """,
    )
    p.add_argument("--dir", metavar="PATH", help="Memory directory to scan (default: ./memory)")
    p.add_argument("--index", metavar="FILE", help="Index file to check for orphan references")
    p.add_argument("--max-age", type=int, metavar="DAYS", help="Max file age in days before warning (default: 30)")
    p.add_argument("--max-size", type=int, metavar="BYTES", help="Max file size in bytes before warning (default: 51200)")
    p.add_argument("--extensions", nargs="+", metavar="EXT", help="File extensions to scan (default: .md)")
    p.add_argument("--fix", action="store_true", help="Apply automatic fixes (archive old files, flag contradictions)")
    p.add_argument("--dry-run", action="store_true", help="With --fix: show what would be done without doing it")
    p.add_argument("--no-color", action="store_true", help="Disable colored output (plain text)")
    p.add_argument("--config", metavar="FILE", help="Path to memory-health.json config file")
    p.add_argument("--exit-code", action="store_true", help="Exit with non-zero code if issues found")
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Locate config file
    config_path = None
    if args.config:
        config_path = Path(args.config)
    else:
        for candidate in [Path("memory-health.json"), Path("memory/memory-health.json")]:
            if candidate.exists():
                config_path = candidate
                break

    cli_overrides = {
        "memory_dir": args.dir,
        "index_file": args.index,
        "max_age_days": args.max_age,
        "max_size_bytes": args.max_size,
        "extensions": args.extensions,
    }

    cfg = load_config(config_path, cli_overrides)

    report = scan(cfg)
    render(report, cfg, force_plain=args.no_color)

    if args.fix:
        print()
        actions = apply_fixes(report, cfg, dry_run=args.dry_run)
        prefix = "[DRY RUN] " if args.dry_run else ""
        if actions:
            print(f"\n{prefix}Fix actions applied:")
            for a in actions:
                print(f"  {prefix}{a}")
        else:
            print(f"{prefix}No automatic fixes needed.")

    if args.exit_code and (report.has_critical or report.has_warnings):
        sys.exit(1)


if __name__ == "__main__":
    main()
