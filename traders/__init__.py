"""
Traders registry — each module declares:
  SLUG, NAME, PILLAR, SOURCE, METHODS, scan(conn, limit)
"""

from traders import john_crane
from traders import larry_spears
from traders import oshaughnessy
from traders import quantitative_value
from traders import value_investing_made_easy
from traders import way_of_the_turtle
from traders import seven_simple_strategies
from traders import apurva_parikh
from traders import ishaan_agnihotri
from traders import nison
from traders import chande
from traders import oneil
from traders import mcallen

REGISTRY = [
    john_crane,
    larry_spears,
    oshaughnessy,
    quantitative_value,
    value_investing_made_easy,
    way_of_the_turtle,
    seven_simple_strategies,
    apurva_parikh,
    ishaan_agnihotri,
    nison,
    chande,
    oneil,
    mcallen,
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
            return