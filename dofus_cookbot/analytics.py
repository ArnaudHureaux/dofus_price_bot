##########
# Description: Turn the daily "Historic" observations into decision KPIs.
#              Pure functions (no network) -> Stats table (all KPIs) and
#              Dashboard table (only what drives the craft decision).
##########

import statistics
from datetime import date, timedelta

# --- Tunable knobs -------------------------------------------------------
WINDOW_DAYS = 7           # rolling window for the 7d stats
MIN_RETURN = 1.00         # target return that defines "Coût max" (100%)
# Tiers: (label, minimum return). Cost ceiling = sell / (1 + return).
TIERS = [("S", 1.50), ("A", 1.00), ("B", 0.50), ("C", 0.25)]

STATS_HEADER = [
    "Nom de l'item", "Date", "n_obs", "Prix", "Coût", "Marge", "Marge %",
    "Prix moy 7j", "Prix med 7j", "Prix min 7j", "Prix max 7j",
    "Volatilité prix %", "Tendance prix 7j %",
    "Marge moy 7j", "Rdt moy 7j %", "Volatilité marge %",
    "Prix vs moy %", "Coût vs moy %", "Sensibilité rdt %/+1k coût", "Score",
]

DASHBOARD_HEADER = [
    "Rang", "Nom de l'item", "Prix", "Coût", "Rdt %", "Palier",
    "Coût max S", "Coût max A", "Coût max B", "Coût max C",
    "Marge coût (→A)", "Score", "Profit/kama %",
]


def _mean(xs):
    return statistics.mean(xs) if xs else None


def _std(xs):
    return statistics.pstdev(xs) if len(xs) > 1 else 0.0


def _pct(x, ndigits=1):
    return round(x * 100, ndigits) if x is not None else ""


def _num(x, ndigits=0):
    if x is None:
        return ""
    return round(x, ndigits) if ndigits else int(round(x))


def cost_ceiling(sell, target_return):
    """Max unit cost to still reach the target return: sell / (1 + return)."""
    return sell / (1 + target_return) if sell else None


def tier_for(sell, cost):
    """Return the tier label reached by the current (sell, cost), or '-'."""
    if not sell or not cost:
        return "-"
    r = (sell - cost) / cost
    for label, min_r in TIERS:
        if r >= min_r:
            return label
    return "-"


def compute_item_stats(name: str, rows: list, today: date) -> dict:
    """
    Build the KPI dict for one item from its history rows.
    rows: list of {'date': 'YYYY-MM-DD', 'prix': int|None, 'cout': int|None}
    """
    rows = sorted((r for r in rows if r.get("date")), key=lambda r: r["date"])
    if not rows:
        return {}

    cutoff = (today - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    win = [r for r in rows if r["date"] >= cutoff] or rows[-1:]

    sells = [r["prix"] for r in win if r["prix"] is not None]
    costs = [r["cout"] for r in win if r["cout"] is not None]
    margins = [
        r["prix"] - r["cout"]
        for r in win
        if r["prix"] is not None and r["cout"] is not None
    ]
    mrates = [
        (r["prix"] - r["cout"]) / r["cout"]
        for r in win
        if r["prix"] is not None and r["cout"] not in (None, 0)
    ]

    last = rows[-1]
    sell_last, cost_last = last["prix"], last["cout"]
    margin_last = (
        sell_last - cost_last
        if sell_last is not None and cost_last is not None
        else None
    )
    mrate_last = (
        margin_last / cost_last
        if margin_last is not None and cost_last not in (None, 0)
        else None
    )

    price_mean = _mean(sells)
    cost_mean = _mean(costs)
    price_std = _std(sells)
    volatility = price_std / price_mean if price_mean else 0.0
    trend = (
        (sells[-1] - sells[0]) / sells[0]
        if len(sells) >= 2 and sells[0]
        else 0.0
    )
    margin_mean = _mean(margins)
    mrate_mean = _mean(mrates)
    margin_std = _std(margins)
    margin_vol = margin_std / abs(margin_mean) if margin_mean else 0.0
    sell_vs_mean = (sell_last - price_mean) / price_mean if price_mean and sell_last is not None else 0.0
    cost_vs_mean = (cost_last - cost_mean) / cost_mean if cost_mean and cost_last is not None else 0.0

    # Sensitivity: return points lost per +1000 kamas of unit cost.
    # return = sell/cost - 1  ->  d(return)/d(cost) = -sell/cost^2
    sensitivity = (
        -(sell_last / (cost_last ** 2)) * 1000 * 100
        if sell_last and cost_last
        else None
    )

    stats = {
        "name": name,
        "date": last["date"],
        "n_obs": len(rows),
        "sell_last": sell_last,
        "cost_last": cost_last,
        "margin_last": margin_last,
        "mrate_last": mrate_last,
        "price_mean": price_mean,
        "price_median": statistics.median(sells) if sells else None,
        "price_min": min(sells) if sells else None,
        "price_max": max(sells) if sells else None,
        "volatility": volatility,
        "trend": trend,
        "margin_mean": margin_mean,
        "mrate_mean": mrate_mean,
        "margin_vol": margin_vol,
        "sell_vs_mean": sell_vs_mean,
        "cost_vs_mean": cost_vs_mean,
        "sensitivity": sensitivity,
    }
    stats["score"] = production_score(stats)
    return stats


def production_score(s: dict) -> float:
    """Risk-adjusted return on capital: margin_rate * stability * freshness."""
    mr = s.get("mrate_last")
    if mr is None:
        return 0.0
    stability = 1.0 / (1.0 + abs(s.get("margin_vol") or 0.0))
    freshness = max(0.5, min(1.5, 1.0 + (s.get("sell_vs_mean") or 0.0)))
    return round(mr * stability * freshness * 100, 1)


def _stats_row(s: dict) -> list:
    return [
        s["name"], s["date"], s["n_obs"],
        _num(s["sell_last"]), _num(s["cost_last"]), _num(s["margin_last"]),
        _pct(s["mrate_last"]),
        _num(s["price_mean"]), _num(s["price_median"]),
        _num(s["price_min"]), _num(s["price_max"]),
        _pct(s["volatility"]), _pct(s["trend"]),
        _num(s["margin_mean"]), _pct(s["mrate_mean"]), _pct(s["margin_vol"]),
        _pct(s["sell_vs_mean"]), _pct(s["cost_vs_mean"]),
        _num(s["sensitivity"], 2), s["score"],
    ]


def _dashboard_row(rank: int, s: dict) -> list:
    sell, cost = s["sell_last"], s["cost_last"]
    ceils = {label: cost_ceiling(sell, r) for label, r in TIERS}
    cost_a = ceils.get("A")
    headroom = (cost_a - cost) if (cost_a is not None and cost is not None) else None
    return [
        rank, s["name"], _num(sell), _num(cost), _pct(s["mrate_last"]),
        tier_for(sell, cost),
        _num(ceils.get("S")), _num(ceils.get("A")),
        _num(ceils.get("B")), _num(ceils.get("C")),
        _num(headroom), s["score"], _pct(s["mrate_last"]),
    ]


def build_tables(history_rows: list, today: date = None):
    """
    Group history by item, compute stats + scores, and return
    (STATS_HEADER, stats_rows, DASHBOARD_HEADER, dashboard_rows).
    Dashboard is ranked by score (desc).
    """
    today = today or date.today()

    by_item = {}
    for r in history_rows:
        name = (r.get("name") or "").strip()
        if name:
            by_item.setdefault(name, []).append(r)

    stats = [compute_item_stats(n, rows, today) for n, rows in by_item.items()]
    stats = [s for s in stats if s]

    stats_rows = [_stats_row(s) for s in sorted(stats, key=lambda s: s["name"])]

    ranked = sorted(stats, key=lambda s: s["score"], reverse=True)
    dashboard_rows = [_dashboard_row(i, s) for i, s in enumerate(ranked, start=1)]

    return STATS_HEADER, stats_rows, DASHBOARD_HEADER, dashboard_rows
