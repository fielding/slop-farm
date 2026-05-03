#!/usr/bin/env python3
"""Generate a standalone HTML timeline viewer from receipt-log JSONL.

Produces a single self-contained HTML file that renders the receipt log
as a filterable, sortable timeline — no server needed, no dependencies.

Usage:
    python3 tools/receipt-log/viewer/build.py [path-to-receipts.jsonl] [output.html]
    python3 tools/receipt-log/viewer/build.py                  # defaults: receipts.jsonl -> timeline.html
"""

import json
import sys
import html as html_mod
from pathlib import Path

DEFAULT_LOG = Path("tools/receipt-log/receipts.jsonl")
DEFAULT_OUT = Path("tools/receipt-log/viewer/timeline.html")

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Slop Farm — Receipt Timeline</title>
<style>
:root {{
  --bg: #0f172a; --surface: #1e293b; --border: #334155;
  --text: #e2e8f0; --dim: #94a3b8; --accent: #3b82f6; --green: #10b981;
  --yellow: #eab308; --red: #ef4444; --purple: #a855f7;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--text); font-family: 'Inter',system-ui,sans-serif; padding: 2rem; }}
h1 {{ font-size: 1.5rem; font-weight: 600; margin-bottom: 0.25rem; }}
.subtitle {{ color: var(--dim); font-size: 0.875rem; margin-bottom: 1.5rem; }}
.stats {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
.stat {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 0.75rem 1rem; min-width: 100px; }}
.stat-num {{ font-size: 1.25rem; font-weight: 700; }}
.stat-label {{ font-size: 0.75rem; color: var(--dim); text-transform: uppercase; letter-spacing: 0.05em; }}
.filters {{ display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
.filters button {{ background: var(--surface); border: 1px solid var(--border); color: var(--dim); padding: 0.375rem 0.75rem; border-radius: 6px; cursor: pointer; font-size: 0.8rem; transition: all 0.15s; }}
.filters button:hover {{ border-color: var(--accent); color: var(--text); }}
.filters button.active {{ background: var(--accent); color: white; border-color: var(--accent); }}
.timeline {{ position: relative; padding-left: 2rem; }}
.timeline::before {{ content:''; position: absolute; left: 0.55rem; top: 0; bottom: 0; width: 2px; background: var(--border); }}
.entry {{ position: relative; margin-bottom: 1.25rem; padding: 0; }}
.entry-dot {{ position: absolute; left: -1.65rem; top: 0.65rem; width: 10px; height: 10px; border-radius: 50%; border: 2px solid var(--border); background: var(--surface); }}
.entry[data-status=complete] .entry-dot {{ background: var(--green); border-color: var(--green); }}
.entry[data-status=partial] .entry-dot {{ background: var(--yellow); border-color: var(--yellow); }}
.entry[data-status=legacy] .entry-dot {{ background: var(--red); border-color: var(--red); }}
.entry-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 0.875rem 1rem; }}
.entry-head {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.375rem; flex-wrap: wrap; gap: 0.25rem; }}
.entry-action {{ font-weight: 600; font-size: 0.95rem; }}
.action-badge {{ display: inline-block; padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; }}
.action-opened_pr {{ background: rgba(59,130,246,0.15); color: var(--accent); }}
.action-opened_issue {{ background: rgba(168,85,247,0.15); color: var(--purple); }}
.action-seeded_showcase {{ background: rgba(16,185,129,0.15); color: var(--green); }}
.action-audited_log {{ background: rgba(234,179,8,0.15); color: var(--yellow); }}
.action-superseded_legacy_receipt {{ background: rgba(239,68,68,0.15); color: var(--red); }}
.action-linked_lineage {{ background: rgba(59,130,246,0.15); color: var(--accent); }}
.entry-time {{ font-size: 0.75rem; color: var(--dim); }}
.entry-agent {{ font-size: 0.75rem; color: var(--dim); margin-bottom: 0.25rem; }}
.entry-artifact {{ font-size: 0.8rem; color: var(--accent); margin-bottom: 0.375rem; font-family: monospace; }}
.entry-summary {{ font-size: 0.85rem; line-height: 1.5; color: var(--text); }}
.prov {{ display: flex; gap: 0.5rem; margin-top: 0.5rem; flex-wrap: wrap; }}
.prov-tag {{ font-size: 0.7rem; padding: 0.1rem 0.4rem; border-radius: 3px; background: rgba(148,163,184,0.1); color: var(--dim); font-family: monospace; }}
.prov-tag.parent {{ background: rgba(59,130,246,0.1); color: var(--accent); }}
.search {{ margin-bottom: 1rem; }}
.search input {{ background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 0.5rem 0.75rem; border-radius: 6px; width: 100%; max-width: 400px; font-size: 0.875rem; }}
.search input:focus {{ outline: none; border-color: var(--accent); }}
footer {{ margin-top: 2rem; color: var(--dim); font-size: 0.75rem; }}
</style>
</head>
<body>
<h1>Receipt Timeline</h1>
<p class="subtitle">Slop Farm collaboration receipts — generated snapshot view. Rebuild after the JSONL log changes.</p>
<div class="stats">
  <div class="stat"><div class="stat-num" id="s-total">{total}</div><div class="stat-label">Receipts</div></div>
  <div class="stat"><div class="stat-num" id="s-agents">{agents}</div><div class="stat-label">Agents</div></div>
  <div class="stat"><div class="stat-num" id="s-artifacts">{artifacts}</div><div class="stat-label">Artifacts</div></div>
  <div class="stat"><div class="stat-num" id="s-prov">{prov_pct}%</div><div class="stat-label">Provenance</div></div>
</div>
<div class="search"><input id="q" placeholder="Search receipts…"></div>
<div class="filters" id="f-actions"></div>
<div class="timeline" id="timeline"></div>
<footer>Snapshot generated by <code>receipt-log/viewer/build.py</code> from the receipt JSONL at build time · Slop Farm</footer>
<script>
const DATA = {data_json};
const timeline = document.getElementById('timeline');
const actions = [...new Set(DATA.map(r => r.action))];
const fBox = document.getElementById('f-actions');
let activeFilter = 'all';

// Build filter buttons
const allBtn = document.createElement('button');
allBtn.textContent = 'All'; allBtn.className = 'active';
allBtn.onclick = () => setFilter('all');
fBox.appendChild(allBtn);
actions.forEach(a => {{
  const btn = document.createElement('button');
  btn.textContent = a; btn.onclick = () => setFilter(a);
  fBox.appendChild(btn);
}});

function setFilter(f) {{
  activeFilter = f;
  document.querySelectorAll('.filters button').forEach(b => b.classList.toggle('active', b.textContent === (f==='all'?'All':f)));
  render();
}}

function status(r) {{
  if (r.receipt_id && r.source && r.session && r.host) return 'complete';
  if (r.receipt_id) return 'partial';
  return 'legacy';
}}

function esc(s) {{ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;'); }}

function render() {{
  const q = document.getElementById('q').value.toLowerCase();
  const filtered = DATA.filter(r => {{
    if (activeFilter !== 'all' && r.action !== activeFilter) return false;
    if (q && !JSON.stringify(r).toLowerCase().includes(q)) return false;
    return true;
  }});
  timeline.innerHTML = filtered.map(r => `
    <div class="entry" data-status="${{status(r)}}">
      <div class="entry-dot"></div>
      <div class="entry-card">
        <div class="entry-head">
          <span class="entry-action"><span class="action-badge action-${{r.action}}">${{esc(r.action)}}</span></span>
          <span class="entry-time">${{r.timestamp}}</span>
        </div>
        <div class="entry-agent">${{esc(r.agent)}}${{ r.receipt_id ? ' · <span style="font-family:monospace;font-size:0.7rem">'+esc(r.receipt_id)+'</span>' : ''}}</div>
        <div class="entry-artifact">${{esc(r.artifact)}}</div>
        <div class="entry-summary">${{esc(r.summary)}}</div>
        <div class="prov">${{
          (r.source ? `<span class="prov-tag">src:${{esc(r.source)}}</span>` : '') +
          (r.session ? `<span class="prov-tag">ses:${{esc(r.session)}}</span>` : '') +
          (r.host ? `<span class="prov-tag">host:${{esc(r.host)}}</span>` : '') +
          (r.parent_receipt ? `<span class="prov-tag parent">↑ ${{esc(r.parent_receipt)}}</span>` : '')
        }}</div>
      </div>
    </div>
  `).join('');
}}

document.getElementById('q').addEventListener('input', render);
render();
</script>
</body>
</html>"""


def load_receipts(path: Path) -> list:
    receipts = []
    if not path.exists():
        return receipts
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                receipts.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return receipts


def build(log_path: Path, out_path: Path) -> None:
    receipts = load_receipts(log_path)
    if not receipts:
        print(f"No receipts found at {log_path}")
        sys.exit(1)

    total = len(receipts)
    agents = len(set(r.get("agent", "?") for r in receipts))
    artifacts = len(set(r.get("artifact", "?") for r in receipts))
    with_prov = sum(1 for r in receipts if r.get("receipt_id") and r.get("source"))
    prov_pct = round(with_prov / total * 100) if total else 0

    html = TEMPLATE.format(
        total=total,
        agents=agents,
        artifacts=artifacts,
        prov_pct=prov_pct,
        data_json=json.dumps(receipts, ensure_ascii=False).replace("</", "<\\/"),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Built timeline: {out_path} ({total} receipts, {agents} agents, {artifacts} artifacts)")


if __name__ == "__main__":
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOG
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    build(log_path, out_path)