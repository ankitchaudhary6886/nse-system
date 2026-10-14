"""HybridSwingNet (imports as ``stockxpert``) - vendored research integration.

WHAT THIS IS
------------
A *research-only* vendor of https://github.com/Onkarj012/HybridSwingNet pinned at
commit ``UPSTREAM_COMMIT`` below. The upstream authors' own README reports that
their pre-registered walk-forward out-of-sample protocol produced a NEGATIVE
result (-64.3% return, Sharpe -0.79). Treat every number this package produces
as a measurement to be reported honestly, never as a tradeable signal.

DESIGN RULE (house rule: a missing dependency must never blank the live UI)
--------------------------------------------------------------------------
Importing this package must never raise. Nothing at module import time pulls in
torch/pandas/yfinance/transformers. Use :func:`import_stockxpert` or
:func:`probe_dependencies`, both of which return a status object instead of
raising.

Nothing in here is imported by the production terminal; it is opt-in research.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

# Upstream commit this vendor was taken from (git ls-remote HEAD at vendor time).
UPSTREAM_COMMIT = "901bcd223363a08eab371a8e4903d10201f88f55"
UPSTREAM_REPO = "https://github.com/Onkarj012/HybridSwingNet"
UPSTREAM_DIR = Path(__file__).resolve().parent / "upstream"
UPSTREAM_SRC = UPSTREAM_DIR / "src"
UPSTREAM_SCRIPTS = UPSTREAM_DIR / "scripts"

#: Modules the core V3 model + dataset path needs. Heaviest first.
CORE_DEPENDENCIES = ("numpy", "pandas", "sklearn", "torch", "yaml")

#: Needed only by parts we do not use (plots / release scripts).
SOFT_DEPENDENCIES = ("matplotlib", "seaborn", "sentencepiece", "statsmodels", "scipy")


def ensure_upstream_path() -> str | None:
    """Put the vendored ``src/`` on ``sys.path``. Never raises.

    Returns the path that was added, or ``None`` if the vendor directory is
    missing.
    """
    try:
        if not UPSTREAM_SRC.is_dir():
            return None
        path = str(UPSTREAM_SRC)
        if path not in sys.path:
            sys.path.insert(0, path)
        return path
    except Exception:
        return None


def ensure_scripts_path() -> str | None:
    """Put the vendored ``scripts/`` on ``sys.path`` (for train_v3 helpers)."""
    try:
        if not UPSTREAM_SCRIPTS.is_dir():
            return None
        path = str(UPSTREAM_SCRIPTS)
        if path not in sys.path:
            sys.path.insert(0, path)
        return path
    except Exception:
        return None


def probe_dependencies() -> dict[str, Any]:
    """Report which dependencies are importable. Never raises."""
    report: dict[str, Any] = {"core": {}, "soft": {}, "missing_core": [], "missing_soft": []}
    for name in CORE_DEPENDENCIES:
        try:
            mod = importlib.import_module(name)
            report["core"][name] = getattr(mod, "__version__", "unknown")
        except Exception as exc:  # noqa: BLE001 - deliberately broad, must not raise
            report["core"][name] = f"MISSING ({type(exc).__name__}: {exc})"
            report["missing_core"].append(name)
    for name in SOFT_DEPENDENCIES:
        try:
            mod = importlib.import_module(name)
            report["soft"][name] = getattr(mod, "__version__", "unknown")
        except Exception as exc:  # noqa: BLE001
            report["soft"][name] = f"missing ({type(exc).__name__})"
            report["missing_soft"].append(name)
    return report


def import_stockxpert() -> tuple[Any | None, str]:
    """Import the vendored ``stockxpert`` package.

    Returns ``(module, reason)``. On success ``reason`` is ``""``. On any
    failure - missing vendor directory, missing heavy dependency, broken
    upstream code - returns ``(None, <human readable reason>)`` and NEVER
    raises. This is the only sanctioned way for app code to reach the vendor.
    """
    if not UPSTREAM_SRC.is_dir():
        return None, f"vendored upstream missing at {UPSTREAM_SRC}"
    ensure_upstream_path()
    try:
        module = importlib.import_module("stockxpert")
    except Exception as exc:  # noqa: BLE001 - must not propagate into the UI
        return None, f"import stockxpert failed: {type(exc).__name__}: {exc}"
    return module, ""


def import_stockxpert_v3() -> tuple[dict[str, Any], str]:
    """Import the V3 model/dataset entry points.

    Returns ``(namespace, reason)`` where ``namespace`` holds the V3 callables.
    Returns an empty namespace plus a reason string when unavailable. Never
    raises.
    """
    _, reason = import_stockxpert()
    if reason:
        return {}, reason

    namespace: dict[str, Any] = {}
    targets = {
        "StockXpertModelV3": "stockxpert.v3.models.stockxpert",
        "StockXpertV3Loss": "stockxpert.v3.models.losses",
        "SampleBuilder": "stockxpert.v3.dataset.make_samples",
        "StockXpertV3Dataset": "stockxpert.v3.dataset.dataloaders",
        "cross_sectional_split": "stockxpert.v3.dataset.splits",
        "time_split": "stockxpert.v3.dataset.splits",
        "assert_no_leakage": "stockxpert.v3.dataset.splits",
        "ScalerGroup": "stockxpert.dataset.scaling",
        "FeatureBuilder": "stockxpert.features.builder",
        "Trainer": "stockxpert.v3.training.train_loop",
    }
    for attr, module_name in targets.items():
        try:
            namespace[attr] = getattr(importlib.import_module(module_name), attr)
        except Exception as exc:  # noqa: BLE001
            return {}, f"import {module_name}.{attr} failed: {type(exc).__name__}: {exc}"
    return namespace, ""


__all__ = [
    "UPSTREAM_COMMIT",
    "UPSTREAM_REPO",
    "UPSTREAM_DIR",
    "UPSTREAM_SRC",
    "ensure_upstream_path",
    "ensure_scripts_path",
    "probe_dependencies",
    "import_stockxpert",
    "import_stockxpert_v3",
]
