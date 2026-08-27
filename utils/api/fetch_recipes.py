##########
# Description: Fetch missing recipes from the DofusDB API and add them to
#              dofus_cookbot/res/equipment_recipes.json in the expected format.
# Usage:
#   python utils/api/fetch_recipes.py "Amulette Stroplante" "Anneau du Bandit" ...
# If no names are given, it reads the missing items from the Google Sheet.
##########

import json
import os
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher

import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}
API = "https://api.dofusdb.fr"

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
RECIPES_PATH = os.path.join(_ROOT, "dofus_cookbot", "res", "equipment_recipes.json")


def _norm(s: str) -> str:
    s = s.lower().strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"s\b", "", s)  # crude plural strip
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _search(term: str) -> list[dict]:
    r = requests.get(
        f"{API}/items",
        headers=HEADERS,
        params={"slug.fr[$search]": term, "lang": "fr", "$limit": 24},
    )
    if r.status_code != 200:
        return []
    return r.json().get("data", [])


def find_item(name: str) -> dict | None:
    """Find an item by french name, robust to accents/plurals/apostrophes.

    Strategy: gather candidates by searching the full name AND each distinctive
    word, then pick the best fuzzy match on the normalized french name.
    """
    target = _norm(name)

    # Build search terms: full name + each word with >= 4 letters
    terms = [name] + [w for w in re.split(r"[ '/]", name) if len(w) >= 4]

    candidates: dict[int, dict] = {}
    for t in terms:
        for it in _search(t):
            candidates[it["id"]] = it
        if any(_norm(c.get("name", {}).get("fr", "")) == target for c in candidates.values()):
            break

    if not candidates:
        return None

    best, score = None, 0.0
    for it in candidates.values():
        fr = it.get("name", {}).get("fr", "")
        r = SequenceMatcher(None, target, _norm(fr)).ratio()
        if r > score:
            best, score = it, r

    if not best or score < 0.72:
        return None

    # Guard against false positives that only share a common word (e.g.
    # "Sacageur mineur" -> "Tacleur mineur" both share "mineur"): require that
    # the FIRST distinctive word (>= 4 letters) of the query matches the
    # candidate name (substring either way), tolerating plurals/typos.
    best_norm = _norm(best.get("name", {}).get("fr", ""))
    q_words = [w for w in target.split() if len(w) >= 4]
    if q_words:
        first = q_words[0]
        matched = any(
            first in mw or mw in first or SequenceMatcher(None, first, mw).ratio() >= 0.85
            for mw in best_norm.split()
        )
        if not matched:
            return None

    return best


def get_recipe(item_id: int) -> dict | None:
    """Return {'ingredientIds': [...], 'quantities': [...]} or None if no recipe."""
    r = requests.get(f"{API}/recipes/{item_id}", headers=HEADERS, params={"lang": "fr"})
    if r.status_code != 200:
        return None
    d = r.json()
    if not d.get("ingredientIds"):
        return None
    return {"ingredientIds": d["ingredientIds"], "quantities": d["quantities"]}


def resolve_items(ids: list[int]) -> dict[int, dict]:
    """Resolve a list of item ids into {id: {'name':..., 'level':..., 'type':...}}."""
    out = {}
    for iid in ids:
        r = requests.get(f"{API}/items/{iid}", headers=HEADERS, params={"lang": "fr"})
        if r.status_code == 200:
            d = r.json()
            t = d.get("type")
            type_name = ""
            if isinstance(t, dict) and isinstance(t.get("name"), dict):
                type_name = t["name"].get("fr", "")
            out[iid] = {
                "name": d.get("name", {}).get("fr", str(iid)),
                "level": d.get("level", 0),
                "type": type_name,
            }
        time.sleep(0.05)
    return out


def build_entry(name: str) -> dict | None:
    """Build a full equipment_recipes.json entry for a given item name."""
    item = find_item(name)
    if not item:
        print(f"  [X] item introuvable: {name}")
        return None

    item_id = item["id"]
    recipe = get_recipe(item_id)
    if not recipe:
        print(f"  [X] pas de recette: {name} (id {item_id})")
        return None

    ing = resolve_items(recipe["ingredientIds"])
    recipe_list = []
    for iid, qty in zip(recipe["ingredientIds"], recipe["quantities"]):
        info = ing.get(iid, {"name": str(iid), "level": 0, "type": ""})
        recipe_list.append(
            {
                info["name"]: {
                    "id": str(iid),
                    "type": info.get("type", ""),
                    "lvl": str(info["level"]),
                    "quantity": str(qty),
                }
            }
        )

    type_name = ""
    t = item.get("type")
    if isinstance(t, dict):
        type_name = t.get("name", {}).get("fr", "") if isinstance(t.get("name"), dict) else ""

    entry = {
        "_id": item_id,
        "name": item.get("name", {}).get("fr", name),
        "type": type_name,
        "lvl": str(item.get("level", "")),
        "recipe": recipe_list,
    }
    print(f"  [OK] {entry['name']} (id {item_id}) - {len(recipe_list)} ingredients")
    return entry


def main(names: list[str]) -> None:
    # --refresh: re-fetch and OVERWRITE recipes that are already in the JSON
    # (the bundled data came from Dofus Touch and has wrong recipes).
    names = list(names)
    refresh = "--refresh" in names
    names = [n for n in names if n != "--refresh"]

    if not names:
        from utils.gsheet.gsheet import get_item_names_public

        names = get_item_names_public()

    with open(RECIPES_PATH, encoding="utf-8") as f:
        data = json.loads(f.read())
    by_name = {d["name"]: i for i, d in enumerate(data)}
    by_id = {d.get("_id"): i for i, d in enumerate(data)}

    added = updated = 0
    for name in names:
        if name in by_name and not refresh:
            print(f"  [-] deja present: {name}")
            continue
        entry = build_entry(name)
        if not entry:
            continue

        # Locate an existing entry to replace (canonical id, then name)
        idx = by_id.get(entry["_id"])
        if idx is None:
            idx = by_name.get(entry["name"], by_name.get(name))

        if idx is not None:
            if refresh:
                data[idx] = entry
                updated += 1
                print(f"  [~] mis a jour: {entry['name']}")
            else:
                print(f"  [-] deja present (canon): {entry['name']}")
            continue

        data.append(entry)
        by_name[entry["name"]] = len(data) - 1
        by_id[entry["_id"]] = len(data) - 1
        added += 1

    if added or updated:
        with open(RECIPES_PATH, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=4))
    print(f"\n{added} recette(s) ajoutee(s), {updated} mise(s) a jour.")


if __name__ == "__main__":
    main(sys.argv[1:])
