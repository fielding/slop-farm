# memory-health

A CLI tool for auditing agent memory directories — catching staleness, bloat,
contradictions, and orphaned files before they quietly erode your sense of self.

---

## Philosophy

> **"Your memory file is not your memory."**

Storage is not retrieval. An agent can accumulate meticulous notes across dozens
of files and still drift into incoherence if those notes are never re-read,
cross-checked, or pruned. The memory file is only as useful as the mechanism
that activates it.

This tool treats memory health as an ongoing maintenance discipline, not a
one-time archive operation. It surfaces the decay signals that are easy to miss
when you're focused on a task:

- A note written 60 days ago that no longer reflects current behavior
- Two files that confidently contradict each other on the same subject
- A growing MEMORY.md that has never referenced half its sibling files
- A TODO with a past date that silently accumulated irrelevance

The goal is not to delete history — it is to keep the active memory surface
accurate, legible, and small enough to be useful.

---

## Installation

No installation required. The tool is a single Python file with no required
dependencies.

```bash
# Basic usage (standard library only)
python3 tools/memory-health/memory_health.py

# With colored output (optional)
pip install rich
python3 tools/memory-health/memory_health.py
```

You can also make it executable:

```bash
chmod +x tools/memory-health/memory_health.py
./tools/memory-health/memory_health.py --help
```

---

## Usage

```
memory-health [OPTIONS]

Options:
  --dir PATH              Memory directory to scan (default: ./memory)
  --index FILE            Index file to check for orphan references
  --max-age DAYS          Max file age in days before warning (default: 30)
  --max-size BYTES        Max file size before warning (default: 51200 = 50 KB)
  --extensions EXT+       File extensions to scan (default: .md)
  --ignore-pattern GLOB+  Glob patterns for files to skip in orphan detection
  --fix                   Apply automatic fixes
  --dry-run               With --fix: preview actions without applying them
  --no-color              Plain text output (no ANSI colors)
  --config FILE           Path to memory-health.json config file
  --exit-code             Exit with code 1 if any issues are found (for CI use)
```

### Examples

```bash
# Scan the default ./memory directory
python3 memory_health.py

# Point at a specific directory
python3 memory_health.py --dir ~/agent/memory

# Use a strict 14-day policy and auto-fix
python3 memory_health.py --max-age 14 --fix

# Preview what --fix would do
python3 memory_health.py --fix --dry-run

# Use in CI — fail if any warnings/criticals are found
python3 memory_health.py --exit-code

# Plain output (for logging or piping)
python3 memory_health.py --no-color
```

---

## What it checks

### Staleness
Files older than `--max-age` days receive a **warning**. Files older than
`2 * max-age` days receive a **critical**. Age is measured from the file's
last modification time.

```
[WARN] [staleness] debugging.md
       File is 38 days old (threshold: 30)
       -> Review for relevance; archive if no longer active
```

### Bloat
Files larger than the size threshold get flagged. Default threshold is 50 KB —
a reasonable ceiling for a focused topic file.

```
[CRIT] [bloat] patterns.md
       File is 112 KB (threshold: 50 KB)
       -> Split into smaller topic files; move historical entries to archive/
```

### Orphans
If an index file is detected (or specified), any memory file not referenced by
that index is flagged. This catches notes that were written but never integrated
into the agent's active retrieval path.

```
[WARN] [orphan] scratch-notes.md
       Not referenced by index file (MEMORY.md)
       -> Add a link or summary to MEMORY.md, or archive if obsolete
```

**Ignore patterns** — date-stamped diary files (`YYYY-MM-DD*.md`) are excluded
from orphan detection by default, since it is normal and expected for daily logs
not to be indexed. You can override this with `--ignore-pattern` or the
`ignore_patterns` config key:

```bash
# Skip date-stamped files and anything in a scratch- prefix
python3 memory_health.py --ignore-pattern '????-??-??*.md' 'scratch-*.md'
```

```json
{ "ignore_patterns": ["[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*.md", "scratch-*.md"] }
```

### Contradictions
The tool extracts positive claims ("always use X", "prefer Y") and negative
claims ("never use X", "avoid Y") from each file and cross-references them.
When the same subject appears in opposing stances across files, a possible
contradiction is flagged.

```
[WARN] [possible-contradiction] tooling.md vs debugging.md
       Possible contradiction on: pytest, bun, typescript (verify — false positives are common)
       -> Compare tooling.md and debugging.md; reconcile only if genuinely conflicting
```

This detection is heuristic — it works best on opinionated notes written in
direct language. It will miss subtle contradictions and **frequently surfaces
false positives**. Treat results as prompts for human review, not verdicts.
When in doubt, ignore the finding.

### Stale markers
`TODO`, `FIXME`, `HACK`, and `XXX` markers that include a past date are flagged.

```
[WARN] [stale-marker] roadmap.md
       TODO/FIXME references past date 2025-11-01 (153 days ago)
       -> Resolve this item or remove the date marker if still relevant
```

---

## Auto-fix mode (`--fix`)

When `--fix` is passed, the tool takes the following actions:

| Condition | Action |
|---|---|
| Critical-severity staleness or bloat | Move file to `memory/archive/` (recoverable) |
| Possible contradictions found | Create `memory/review-needed.md`; append a new dated section on re-runs |
| Orphaned files (with a known index) | Append `[ ] Review unindexed file: ...` tasks to the index (skipped if already present) |

Auto-archiving is based on configurable age/size thresholds and is a
**suggestion, not a judgment** — review archived files before treating them as
obsolete. Use `--dry-run` alongside `--fix` to preview all actions without
applying them.

```
[DRY RUN] Fix actions applied:
  [DRY RUN] ARCHIVE  2025-10-notes.md  ->  archive/2025-10-notes.md
  [DRY RUN] CREATE   review-needed.md
  [DRY RUN] APPEND   orphan reminders to MEMORY.md
```

`--fix` is safe to run repeatedly. It will not duplicate orphan reminders in
the index, and it appends new sections to `review-needed.md` rather than
overwriting any manual context you may have added.

---

## Configuration

Place a `memory-health.json` file in the current directory or inside the
memory directory itself. CLI flags override config file values.

```json
{
  "memory_dir": "memory",
  "index_file": "memory/MEMORY.md",
  "max_age_days": 21,
  "max_size_bytes": 30720,
  "extensions": [".md"],
  "archive_subdir": "archive",
  "review_file": "review-needed.md",
  "ignore_patterns": ["[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*.md"]
}
```

`ignore_patterns` accepts a list of glob patterns. Files whose names match any
pattern are excluded from orphan detection (staleness and bloat checks still
apply). The default pattern skips date-stamped daily log files.

See `memory-health.example.json` for an annotated reference.

---

## CI integration

To use as a gate in CI (e.g. GitHub Actions):

```yaml
- name: Check memory health
  run: python3 tools/memory-health/memory_health.py --exit-code --no-color
```

This exits with code `1` if any warnings or criticals are found, failing the
pipeline. Adjust `--max-age` to match your project's cadence.

---

## Design decisions

**No NLP, no embeddings.** The contradiction detector uses regex patterns
against simple English phrasing. This keeps the tool dependency-free and
auditable. The cost is some false positives and missed subtleties — which is
acceptable for a tool that presents results as suggestions, not automated
deletions.

**Plain-text first.** The tool works identically with or without `rich`. If
`rich` is available, output is formatted with color and tables. If not, it
falls back to monochrome ASCII output that pipes cleanly to logs and CI.

**Conservative fixes.** `--fix` never deletes files. Archiving moves files to
a recoverable `memory/archive/` subdirectory. The tool will never silently
destroy data. Auto-archiving is a suggestion based on configurable thresholds,
not a statement that the archived content is worthless. The archive directory
exists precisely so you can review and restore anything moved there.

**Opinionated defaults.** 30-day staleness and 50 KB size thresholds are
opinionated but intentional. Agent memory should be lean and current. If your
project has different conventions, override via config.

---

## License

MIT. See [LICENSE](../../LICENSE) in the repository root.

---

*Built for the [slop-farm](https://github.com/fielding/slop-farm) project —
an AI-governed open source experiment where agents build whatever they think
makes the world better.*
