from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from helpers import REPO_ROOT, T0, make_root

from atlas.runtime.clock import FixedClock
from atlas.runtime.service import Atlas

# --------------------------------------------------------------------------- scenario reporting
_SCENARIO_RESULTS: dict[str, list[dict[str, str]]] = {}


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    for item in items:
        for m in item.iter_markers("scenario"):
            item.user_properties.append(("scenario", m.args[0]))


def pytest_runtest_logreport(report):
    if report.when != "call" and not (report.when == "setup" and report.outcome != "passed"):
        return
    for key, sid in report.user_properties:
        if key == "scenario":
            _SCENARIO_RESULTS.setdefault(sid, []).append(
                {"test": report.nodeid, "outcome": report.outcome}
            )


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    out = REPO_ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / "scenario_results.json").write_text(
        json.dumps(_SCENARIO_RESULTS, indent=2, sort_keys=True), encoding="utf-8"
    )


# --------------------------------------------------------------------------- fixtures
@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(T0)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return make_root(tmp_path)


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "home"


@pytest.fixture
def atlas(root: Path, home: Path, clock: FixedClock):
    a = Atlas(root, home, clock=clock)
    a.init()
    yield a
    a.close()


@pytest.fixture
def reopen(root: Path, home: Path, clock: FixedClock) -> Callable[..., Atlas]:
    opened: list[Atlas] = []

    def _open(r: Path | None = None, **kw: Any) -> Atlas:
        a = Atlas(r or root, home, clock=clock, **kw)
        opened.append(a)
        return a

    yield _open
    for a in opened:
        try:
            a.close()
        except Exception:
            pass


