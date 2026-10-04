"""Build the static GitHub Pages status page (index.html at the repo root).

GitHub Pages can only serve static files — it cannot run ATLAS. This script runs the
real test suite, validation report and Phase 1 demo locally and bakes their actual
output into index.html, so the page always reflects what the code really did.

Usage:  python scripts/build_site.py      (then commit index.html)
"""

from __future__ import annotations

import html
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.version import ATLAS_VERSION, PHASE  # noqa: E402


def run(args: list[str]) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return p.returncode, p.stdout + p.stderr


def parse_report(md: str) -> tuple[str, dict[str, int], list[list[str]]]:
    suite = re.search(r"Full test suite: `([^`]*)`", md)
    counts = {k: int(v) for k, v in re.findall(r"^\| (PASS|FAIL|BLOCKED|NOT IMPLEMENTED) \| (\d+) \|$", md, re.M)}
    rows = [
        [c.strip().strip("*") for c in line.strip("|").split("|")]
        for line in md.splitlines()
        if re.match(r"^\| T\d{3} \|", line)
    ]
    return (suite.group(1) if suite else "unknown"), counts, rows


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    rc_val, _ = run(["scripts/validation_report.py"])
    rc_demo, demo_out = run(["scripts/phase1_demo.py"])
    md = (ROOT / "reports" / "VALIDATION_REPORT.md").read_text(encoding="utf-8")
    suite, counts, rows = parse_report(md)
    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    commit = git.stdout.strip() or "uncommitted"
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ok = rc_val == 0 and rc_demo == 0

    def badge(status: str) -> str:
        cls = {"PASS": "pass", "FAIL": "fail", "BLOCKED": "blocked"}.get(status, "ni")
        return f'<span class="badge {cls}">{html.escape(status)}</span>'

    table_rows = "\n".join(
        f"<tr><td class='mono'>{html.escape(r[0])}</td><td>{html.escape(r[1])}</td><td>{badge(r[2])}</td>"
        f"<td class='num'>{html.escape(r[3])}</td><td class='muted'>{html.escape(r[4])}</td></tr>"
        for r in rows
    )
    demo_clean = re.sub(r"/[^\s]*atlas_demo_[^\s]*", "&lt;temp&gt;", html.escape(demo_out))

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ATLAS Status</title>
<style>
:root {{
  --bg:#f7f7f5; --panel:#ffffff; --ink:#1b1d21; --muted:#5d636e; --line:#e2e3e0;
  --pass:#1f7a4d; --pass-bg:#e3f3ea; --fail:#b42318; --fail-bg:#fbe7e5;
  --ni:#5d636e; --ni-bg:#eeefec; --blocked:#9a6700; --blocked-bg:#fbf1d9; --accent:#2d5bd7;
  --code-bg:#14161a; --code-ink:#d8dde6;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg:#111317; --panel:#181b20; --ink:#e7e9ee; --muted:#9aa1ad; --line:#2a2e35;
    --pass:#5fd39a; --pass-bg:#16301f; --fail:#ff8a7a; --fail-bg:#3a1714;
    --ni:#9aa1ad; --ni-bg:#23272d; --blocked:#f2c262; --blocked-bg:#3a2d10; --accent:#8fb0ff;
    --code-bg:#0b0c0f; --code-ink:#cfd5df;
  }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
main {{ max-width:1040px; margin:0 auto; padding:40px 16px 64px; }}
h1 {{ font-size:28px; margin:0 0 4px; letter-spacing:-0.01em; }}
h2 {{ font-size:18px; margin:36px 0 12px; }}
p {{ margin:0 0 12px; }}
a {{ color:var(--accent); }}
.muted {{ color:var(--muted); }}
.mono, code, pre {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
.notice {{ border:1px solid var(--line); background:var(--panel); border-radius:10px; padding:14px 16px; margin:20px 0; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-top:20px; }}
.tile {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
.tile .k {{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }}
.tile .v {{ font-size:26px; font-weight:650; margin-top:2px; }}
.wrap {{ overflow-x:auto; background:var(--panel); border:1px solid var(--line); border-radius:10px; }}
table {{ border-collapse:collapse; width:100%; min-width:640px; }}
th, td {{ text-align:left; padding:9px 12px; border-bottom:1px solid var(--line); vertical-align:top; font-size:14px; }}
th {{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }}
tr:last-child td {{ border-bottom:none; }}
td.num {{ text-align:right; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:600; white-space:nowrap; }}
.badge.pass {{ color:var(--pass); background:var(--pass-bg); }}
.badge.fail {{ color:var(--fail); background:var(--fail-bg); }}
.badge.blocked {{ color:var(--blocked); background:var(--blocked-bg); }}
.badge.ni {{ color:var(--ni); background:var(--ni-bg); }}
pre {{ background:var(--code-bg); color:var(--code-ink); padding:16px; border-radius:10px; overflow-x:auto;
  font-size:12.5px; line-height:1.45; margin:0; }}
details summary {{ cursor:pointer; font-weight:600; margin:8px 0; }}
footer {{ margin-top:40px; font-size:13px; color:var(--muted); }}
</style>
</head>
<body>
<main>
  <h1>ATLAS</h1>
  <p class="muted">Adaptive Trading &amp; Learning Analysis System · v{ATLAS_VERSION} · Phase {PHASE} of 11</p>

  <div class="notice">
    This is a <strong>static status page</strong>. ATLAS itself is a Python program that runs on your
    computer (see the <a href="#" id="qs">README quick start</a>).
    Everything below is the real output of the test suite and the Phase 1 demo at commit
    <code>{html.escape(commit)}</code>. All candidates are <strong>SYNTHETIC</strong>; this is not market
    data and not evidence of profitability. Paper-only; every trade requires human approval.
  </div>

  <div class="tiles">
    <div class="tile"><div class="k">Build</div><div class="v">{"OK" if ok else "FAILED"}</div></div>
    <div class="tile"><div class="k">Test suite</div><div class="v" style="font-size:18px">{html.escape(suite)}</div></div>
    <div class="tile"><div class="k">Scenarios pass</div><div class="v">{counts.get("PASS", 0)}</div></div>
    <div class="tile"><div class="k">Fail</div><div class="v">{counts.get("FAIL", 0)}</div></div>
    <div class="tile"><div class="k">Not implemented</div><div class="v">{counts.get("NOT IMPLEMENTED", 0)}</div></div>
  </div>

  <h2>Validation scenarios (T001–T038)</h2>
  <p class="muted">PASS with PARTIAL coverage means only the Phase 1 (Risk Engine / ledger / state) half of the
  scenario is exercised. Unbuilt functionality is reported as NOT IMPLEMENTED, never as passing.</p>
  <div class="wrap"><table>
    <thead><tr><th>ID</th><th>Scenario</th><th>Status</th><th>Tests</th><th>Coverage</th></tr></thead>
    <tbody>
{table_rows}
    </tbody>
  </table></div>

  <h2>Phase 1 demo output</h2>
  <p class="muted">Start → config → state → capital → risk budget → synthetic candidate → sizing → vetoes →
  persistence → audit → restart → recovery → tamper → HALT.</p>
  <details open><summary>Show full output</summary>
  <pre>{demo_clean}</pre>
  </details>

  <footer>Built {built} by <code>scripts/build_site.py</code>. Not investment advice.</footer>
</main>
<script>
  // Point the README link at this repository when served from <user>.github.io/<repo>/
  (function () {{
    var a = document.getElementById("qs");
    var host = location.hostname, parts = location.pathname.split("/").filter(Boolean);
    if (host.endsWith(".github.io") && parts.length) {{
      a.href = "https://github.com/" + host.split(".")[0] + "/" + parts[0] + "#quick-start";
    }} else {{ a.removeAttribute("href"); }}
  }})();
</script>
</body>
</html>
"""
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote index.html (build {'OK' if ok else 'FAILED'}; {suite}; commit {commit})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
