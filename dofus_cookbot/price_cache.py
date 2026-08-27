##########
# Description: Tiny on-disk price cache so each resource/item is OCR-priced
#              only once per session and craft costs can be assembled from
#              ingredients priced across the three HDV runs.
##########

import json
import os
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(_HERE, "prices_cache.json")


def load() -> dict:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save(cache: dict) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def set_price(cache: dict, name: str, sell: int, cost: int) -> None:
    """Store the sell price (min per-unit) and cost price (max per-unit)."""
    cache[name] = {
        "sell": sell,
        "cost": cost,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_sell(cache: dict, name: str):
    """Per-unit sell price (min); falls back to legacy 'price' entries."""
    entry = cache.get(name)
    if not entry:
        return None
    return entry.get("sell", entry.get("price"))


def get_cost(cache: dict, name: str):
    """Per-unit cost price (max); falls back to legacy 'price' entries."""
    entry = cache.get(name)
    if not entry:
        return None
    return entry.get("cost", entry.get("price"))
