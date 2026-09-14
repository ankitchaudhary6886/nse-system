"""
Traders registry — each module declares:
  SLUG     — url-safe id ("john_crane")
  NAME     — display name
  PILLAR   — "swing" | "funda" | "multi"
  SOURCE   — book / reference
  METHODS  — list of {id, name, description, direction, scan?}
  scan(conn, limit) — returns list of signal dicts

Signal dict shape:
  {symbol, trader, method, direction, signal_type,
   entry, stop, target, confidence, notes, raw}
"""

from traders import john_crane
from traders import larry_spears
from traders import oshaughnessy
from traders import quantitative_value

REGISTRY = [
    john_crane,
    larry_spears,
    oshaughnessy,
    quantitative_value,
]


def list_traders():
    return [{
        "slug": t.SLUG,
        "name": t.NAME,
        "pillar": t.PILLAR,
        "source": t.SOURCE,
        "methods": t.METHODS,
    } for t in REGISTRY]


def get_trader(slug):
    for t in REGISTRY:
        if t.SLUG == slug:
            return t
    return None