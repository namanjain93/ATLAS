"""Run the test suite and report every validation scenario as
PASS / FAIL / BLOCKED / NOT IMPLEMENTED.

* PASS            — scenario tests exist and all passed (coverage column says FULL or PARTIAL)
* FAIL            — at least one scenario test failed
* BLOCKED         — scenario tests exist but were skipped (missing dependency / external data)
* NOT IMPLEMENTED — no tests yet; the owning phase is shown

Unimplemented functionality is never reported as passing.

Usage:  python scripts/validation_report.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from validation_registry import REGISTRY  # noqa: E402

from atlas.version import PHASE  # noqa: E402


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles/CI default to cp1252
    except Exception:
        pass
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-o", "addopts=", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    summary = [ln for ln in proc.stdout.splitlines() if any(w in ln for w in ("passed", "failed", "error"))]
    suite_line = summary[-1].strip() if summary else "(no summary)"
    results = json.loads((ROOT / "reports" / "scenario_results.json").read_text(encoding="utf-8"))

    rows = []
    counts = {"PASS": 0, "FAIL": 0, "BLOCKED": 0, "NOT IMPLEMENTED": 0}
    for sid, (title, phase, cov) in REGISTRY.items():
        tests = results.get(sid, [])
        outcomes = {t["outcome"] for t in tests}
        if not tests:
            status, coverage = "NOT IMPLEMENTED", f"Phase {phase}"
        elif "failed" in outcomes:
            status, coverage = "FAIL", cov or "?"
        elif outcomes == {"skipped"}:
            status, coverage = "BLOCKED", cov or "?"
        else:
            status, coverage = "PASS", cov or "?"
        counts[status] += 1
        rows.append((sid, title, status, len(tests), coverage))

    unknown = sorted(set(results) - set(REGISTRY))
    lines = [
        f"# ATLAS Validation Report — Phase {PHASE}",
        "",
        f"Full test suite: `{suite_line}`",
        "",
        "Scenario validation is design/integration evidence only. **It is not proof of profitability "
        "and not live-market evidence.**",
        "",
        "| Status | Count |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in counts.items()],
        "",
        f"PASS breakdown: FULL {sum(1 for r in rows if r[2] == 'PASS' and r[4] == 'FULL')}, "
        f"PARTIAL {sum(1 for r in rows if r[2] == 'PASS' and r[4] != 'FULL')} "
        "(PARTIAL = only the Phase-1 half of the scenario is exercised; see Coverage).",
        "",
        "| ID | Scenario | Status | Tests | Coverage |",
        "|---|---|---|---|---|",
        *[f"| {r[0]} | {r[1]} | **{r[2]}** | {r[3]} | {r[4]} |" for r in rows],
    ]
    if unknown:
        lines += ["", f"Unregistered scenario tags: {', '.join(unknown)}"]
    report = "\n".join(lines) + "\n"
    (ROOT / "reports" / "VALIDATION_REPORT.md").write_text(report, encoding="utf-8")
    print(report)
    return 0 if proc.returncode == 0 and counts["FAIL"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
