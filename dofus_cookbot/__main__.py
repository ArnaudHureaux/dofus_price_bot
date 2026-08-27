##########
# Author: wildpasta
# Description: Core of Dofus Cooker, handle GUI, autoclick, OCR, and JSON parsing
# Usage: python __main__.py
# Example: python __main__.py
##########

# Python Standard Library Imports
from datetime import datetime
from importlib.resources import files
import json
import os
from random import uniform
from time import sleep

# Avoid an OpenBLAS threading crash when numpy is used for OCR preprocessing
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import sys

# Third-Party Imports
try:
    from PIL import Image, ImageFilter
    from prettytable import PrettyTable
    from pynput.keyboard import Key
    from pynput.mouse import Button as pybtn
    import pyautogui
    import pynput
    import pytesseract
    import pyscreenshot as ImageGrab
except ModuleNotFoundError as e:
    print(f"ModuleNotFoundError: {e}")
    print("Please install the required modules using the following command:")
    print("pip install -r requirements.txt")
    sys.exit(1)

# Local/Application Specific Imports
from dofus_cookbot.gui.gui import create_window, ending_message
from dofus_cookbot.hdv import hdv_for_type
from dofus_cookbot import price_cache

mouse = pynput.mouse.Controller()
keyboard = pynput.keyboard.Controller()
pytesseract.pytesseract.tesseract_cmd = r'D:\tesseract\tesseract.exe'

def do_click(x: int, y: int) -> None:
    """
    purpose:
        Perform a mouse click at the specified coordinates
    input:
        nb (int): Number of clicks to perform
        x (int) : X coordinate of the click
        y (int) : Y coordinate of the click
    output:
        None
    """

    try:
        # Coordinates are already calibrated for the current screen resolution
        # (native coordinates releved with utils/pos_finder/position_finder.py)
        delay = round(uniform(0, 1), 2)
        sleep(delay)  # sleep between 2 and 3 seconds

        pyautogui.moveTo(x, y)
        delay = round(uniform(100, 300), 2) / 1000.0
        sleep(delay)  # between 100 and 300 ms
        pyautogui.click()

    except Exception as e:
        print(f"Error when clicking: {e}")

def _ocr_white_digits(screenshot: Image.Image) -> str:
    """
    purpose:
        Preprocess the panel and OCR only the white price text. Keeping only
        bright, low-saturation pixels drops the colored kamas icon (otherwise
        read as an extra trailing digit) and any coloured UI element.
    input:
        screenshot (Image): screenshot of the panel
    output:
        str: raw OCR text (digits and spaces only)
    """
    import numpy as np

    # The row item thumbnails on the far left bleed bright pixels the OCR reads
    # as a stray leading digit (lot "1" -> "41"); drop that left icon column.
    w, h = screenshot.size
    if w > 80:
        screenshot = screenshot.crop((80, 0, w, h))

    arr = np.array(screenshot.convert("RGB")).astype(int)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    brightness = (r + g + b) / 3
    saturation = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
    text_mask = (brightness > 140) & (saturation < 40)
    binary = np.where(text_mask, 0, 255).astype("uint8")  # black text on white
    clean = Image.fromarray(binary)
    clean = clean.resize((clean.width * 4, clean.height * 4))
    return pytesseract.image_to_string(
        clean, config="--psm 6 -c tessedit_char_whitelist=0123456789 "
    )

def process_image(screenshot: Image.Image, item_name: str) -> dict:
    """
    purpose:
        Process the screenshot of the item's Lot/Prix panel and extract the
        unit price, the price for 10 and the price for 100.
    input:
        screenshot (Image): screenshot of the Lot/Prix panel
        item_name (str)   : name of the item
    output:
        dict: {'price': int, 'price_10': int, 'price_100': int}
    """

    import re

    def _to_int(digits: str) -> int:
        digits = ''.join(filter(str.isdigit, digits))
        return int(digits) if digits else 0

    try:
        # Keep only the white price text (drops the coloured kamas icon)
        text = _ocr_white_digits(screenshot)

        # The panel prints one row per lot, e.g.:
        #   1 1777 ACHETER
        #   10 17 888 ACHETER
        #   100 179999 ACHETER
        # We look for the lot number at the start of a row, then read the price.
        prices = {1: 0, 10: 0, 100: 0}
        for line in text.splitlines():
            # keep only digits and spaces, collapse multiple spaces
            cleaned = re.sub(r'[^\d ]', ' ', line)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if not cleaned:
                continue
            parts = cleaned.split(' ')
            lot = _to_int(parts[0])
            if lot in prices and len(parts) > 1:
                price = _to_int(''.join(parts[1:]))
                if price:
                    prices[lot] = price

        result = {
            'price': prices[1] or 1,
            'price_10': prices[10],
            'price_100': prices[100],
        }
        result['suspicious'] = _check_price_consistency(result)
        return result

    except Exception as e:
        print(f"Error with OCR recognition: {e}")
        return {'price': 1, 'price_10': 0, 'price_100': 0, 'suspicious': True}


def _check_price_consistency(prices: dict) -> bool:
    """
    purpose:
        Sanity-check the OCR read. Only the x10/x100 lots matter (they drive
        the price/cost); the x1 lot is ignored as it is often a lowball single
        listing. Flags a read as suspicious when no lot could be read, or when
        the x10 and x100 per-unit prices diverge by more than ~5x (typical of
        an OCR digit glitch like 179999 -> 1799994).
    input:
        prices (dict): {'price': int, 'price_10': int, 'price_100': int}
    output:
        bool: True if the prices look inconsistent (suspicious), else False.
    """

    p10 = prices.get('price_10', 0) or 0
    p100 = prices.get('price_100', 0) or 0

    # No usable lot price was read at all
    if not p10 and not p100:
        return True

    # Cross-check the two lot per-unit prices when both are available
    if p10 and p100:
        u10, u100 = p10 / 10, p100 / 100
        lo, hi = min(u10, u100), max(u10, u100)
        if lo > 0 and hi / lo > 5:
            return True

    return False


def effective_unit_price(prices: dict) -> int:
    """
    purpose:
        Per-unit craft cost used to fill the sheet's "Coût" column.
        Rule: the MOST EXPENSIVE per-unit price between (x10 / 10) and
        (x100 / 100). The x1 price is ignored (too easy to manipulate with a
        single overpriced/underpriced listing). Falls back to x1 only when no
        lot price is available at all.
    input:
        prices (dict): {'price': int, 'price_10': int, 'price_100': int}
    output:
        int: per-unit price in Kamas (0 if nothing could be read).
    """
    p10 = prices.get('price_10', 0) or 0
    p100 = prices.get('price_100', 0) or 0

    candidates = []
    if p10 > 0:
        candidates.append(p10 / 10)
    if p100 > 0:
        candidates.append(p100 / 100)

    if candidates:
        return round(max(candidates))

    # No lot price available -> fall back to the unit price
    return prices.get('price', 0) or 0


def min_unit_price(prices: dict) -> int:
    """
    purpose:
        Per-unit SELL price used to fill the sheet's "Prix" column: the CHEAPEST
        per-unit listing (the market floor you must match to sell). Unlike the
        cost rule, the x1 lot IS considered here since it is usually the floor.
    input:
        prices (dict): {'price': int, 'price_10': int, 'price_100': int}
    output:
        int: cheapest per-unit price in Kamas (0 if nothing could be read).
    """
    p1 = prices.get('price', 0) or 0
    p10 = prices.get('price_10', 0) or 0
    p100 = prices.get('price_100', 0) or 0

    candidates = []
    if p1 > 1:
        candidates.append(p1)
    if p10 > 0:
        candidates.append(p10 / 10)
    if p100 > 0:
        candidates.append(p100 / 100)

    if candidates:
        return round(min(candidates))

    return p1 or 0


def _save_suspicious_image(panel: Image.Image, item_name: str, prices: dict) -> None:
    """
    purpose:
        Persist the captured HDV panel whenever the OCR result looks wrong, so
        the read can be inspected afterwards. Saved under img/suspicious/.
    """
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out_dir = os.path.join(root, "img", "suspicious")
        os.makedirs(out_dir, exist_ok=True)
        safe = "".join(c if c.isalnum() else "_" for c in item_name)[:40]
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = (
            f"{stamp}_{safe}"
            f"_x1-{prices.get('price')}_x10-{prices.get('price_10')}"
            f"_x100-{prices.get('price_100')}.png"
        )
        panel.save(os.path.join(out_dir, fname))
        print(f"      saved suspicious capture -> img/suspicious/{fname}")
    except Exception as e:
        print(f"      could not save suspicious image: {e}")


def _open_listing(item_name: str) -> Image.Image:
    """Clear the HDV search, type the item name, open its listing panel and
    return a screenshot of the Lot/Prix panel."""
    do_click(881, 378)   # clear research
    sleep(0.4)
    do_click(759, 379)   # search bar
    sleep(0.2)
    keyboard.type(item_name)
    sleep(0.7)
    do_click(1225, 451)  # first result -> unwrap listings
    sleep(1)
    # region = (left, top, width, height), calibrated with region_selector.py
    return pyautogui.screenshot(region=(111, 259, 616 - 111, 627 - 259))


def determine_price(item_name: str, item_quantity: int, item_type: str, item_lvl: int) -> dict:
    """
    purpose:
        Use OCR to determine the price of an item in Dofus
    input:
        item_name (str)    : name of the item to search for
        item_quantity (int): quantity of the item required
        item_type (str)    : type of the item
        item_lvl (int)     : level of the item
    output:
        dict: Dictionary containing the price of the item
    """

    # An empty read (no lot line) usually means the panel did not open in time
    # (server latency) -> wait and retry the search once.
    for attempt in range(2):
        panel = _open_listing(item_name)
        prices = process_image(panel, item_name)
        if prices['price_10'] or prices['price_100']:
            break
        if attempt == 0:
            print(f"  (panneau vide pour {item_name}, nouvel essai...)")
            sleep(1.5)

    warn = "  [!] suspicious OCR" if prices.get('suspicious') else ""
    print(
        f"Prices found for {item_name}: "
        f"x1={prices['price']} | x10={prices['price_10']} | x100={prices['price_100']} Kamas{warn}"
    )

    if prices.get('suspicious'):
        _save_suspicious_image(panel, item_name, prices)

    return {
        'price': prices['price'],
        'price_10': prices['price_10'],
        'price_100': prices['price_100'],
        'suspicious': prices.get('suspicious', False),
    }

def process_item_price(screenshot: Image.Image) -> dict:
    """
    purpose:
        Extract the CHEAPEST listing price of a (non-stackable) item. The panel
        has the same "Lot / Prix" layout as resources, but every row is "Lot 1"
        (items are sold one by one), sorted ascending. We reuse the same line
        parsing (first token = lot, rest = price), keep all "Lot 1" prices and
        return the smallest. Lines like "Niv. 46" or "Prix moyen" are ignored
        because their first token is not a lot number.
    input:
        screenshot (Image): screenshot of the Lot/Prix panel
    output:
        dict: {'price': int, 'candidates': list[int]}
    """
    import re

    def _to_int(digits: str) -> int:
        digits = ''.join(filter(str.isdigit, digits))
        return int(digits) if digits else 0

    try:
        text = _ocr_white_digits(screenshot)

        prices = []
        for line in text.splitlines():
            cleaned = re.sub(r'[^\d ]', ' ', line)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if not cleaned:
                continue
            parts = cleaned.split(' ')
            lot = _to_int(parts[0])
            if lot == 1 and len(parts) > 1:
                price = _to_int(''.join(parts[1:]))
                if price:
                    prices.append(price)

        return {'price': min(prices) if prices else 0, 'candidates': prices}

    except Exception as e:
        print(f"Error with item-price OCR: {e}")
        return {'price': 0, 'candidates': []}


def determine_item_price(item_name: str) -> dict:
    """
    purpose:
        Search an item in the HDV and OCR its cheapest listing price.
    input:
        item_name (str): name of the item to price
    output:
        dict: {'price': int, 'candidates': list[int]}
    """

    # Retry once on an empty read (panel not opened yet -> server latency)
    for attempt in range(2):
        panel = _open_listing(item_name)
        result = process_item_price(panel)
        if result['price']:
            break
        if attempt == 0:
            print(f"  (panneau vide pour {item_name}, nouvel essai...)")
            sleep(1.5)

    print(
        f"Cheapest price for {item_name}: {result['price']} Kamas "
        f"(candidates: {result['candidates']})"
    )
    return result

def parse_recipe_from_json(json_data: list, item_name: str) -> list:
    """
    purpose:
        Parse the JSON data to retrieve the name and level of the specified item's recipe ingredients
    input:
        json_data (list): JSON data containing item information
        item_name (str) : name of the item to search for
    output:
        list: list of dictionaries containing the name, quantity, and level of the recipe ingredients
    """

    try:
        parsed_recipe = []
        for item_data in json_data:
            if item_data['name'] == item_name:
                for recipe_item in item_data.get('recipe', []):
                    for ingredient_name, ingredient_info in recipe_item.items():
                        parsed_recipe.append({
                            'name': ingredient_name,
                            'type': ingredient_info.get('type', ''),
                            'quantity': int(ingredient_info.get('quantity', 0)),
                            'level': int(ingredient_info.get('lvl', 0))
                        })
                break  # Exit loop once the item's recipe is found
        return parsed_recipe
    
    except Exception as e:
        print(f"Error when parsing recipe from JSON: {e}")

def create_report(target: str, parsed_recipe: list) -> None:
    """
    purpose:
        Create a report containing the recipe details for the target item
    input:
        target (str)        : name of the target item
        parsed_recipe (list): list of dictionaries containing the recipe details
    output:
        None
    """

    table = PrettyTable()
    table.field_names = [target, "Level", "Quantity", "Price x1", "Price x10", "Price x100", "Total (x1)", "OK?"]
    total_price_all_items = 0 

    try:
        for resource in parsed_recipe:
            item_name = resource['name']
            item_lvl = resource['level']
            item_quantity = resource['quantity']
            item_price = resource['price']
            item_price_10 = resource.get('price_10', 0)
            item_price_100 = resource.get('price_100', 0)
            flag = "?" if resource.get('suspicious') else "OK"

            total_price = item_quantity * item_price
            total_price_all_items += total_price

            table.add_row([item_name, item_lvl, item_quantity, item_price, item_price_10, item_price_100, total_price, flag])

        # Add 20% tax
        tax = round(total_price_all_items * 0.20)
        total_price_with_tax = total_price_all_items + tax

        # Print total price with tax
        table.add_row(["-" * 10, "-" * 10, "-" * 10, "-" * 10, "-" * 10, "-" * 10, "-" * 10, "-" * 4])
        table.add_row(["Total Price (w/ taxes)", "", "", "", "", "", total_price_with_tax, ""])

        print(table)
    
    except TypeError:
        print("Error when calculating price")
    except Exception as e:
        print(f"Error when creating report: {e}")

def price_item(item_name: str, hdv: str) -> tuple:
    """
    purpose:
        Price a single item in the currently opened HDV.
          - equipment  -> cheapest individual listing (Lot 1); sell = cost
          - resource / consumable -> sell = cheapest per-unit (min),
            cost = max(x10/10, x100/100)
    input:
        item_name (str): name of the item to price
        hdv (str)      : "equipment" | "resource" | "consumable"
    output:
        tuple: (sell:int, cost:int, suspicious:bool)
    """
    if hdv == "equipment":
        price = determine_item_price(item_name).get('price', 0)
        return price, price, price <= 0

    price_info = determine_price(item_name, 0, "", 0)
    sell = min_unit_price(price_info)
    cost = effective_unit_price(price_info)
    suspicious = bool(price_info.get('suspicious')) or cost <= 0
    return sell, cost, suspicious


def format_recipe_detail(parsed_recipe: list) -> str:
    """
    purpose:
        Build a human-readable recipe breakdown by per-unit cost, e.g.
        "1 Bois Vermoulu (3000) + 2 Coton Ancestral (500)".
    input:
        parsed_recipe (list): ingredients with 'name', 'quantity', 'unit_cost'
    output:
        str: the formatted recipe string
    """
    return " + ".join(
        f"{r['quantity']} {r['name']} ({r.get('unit_cost', 0)})" for r in parsed_recipe
    )


def _load_recipes_data() -> list:
    """purpose: load the equipment/recipes JSON bundled in the package."""
    with files("dofus_cookbot.res").joinpath("equipment_recipes.json").open(
        encoding="utf-8"
    ) as f:
        return json.loads(f.read())


def _type_index(data: list) -> dict:
    """purpose: map each known item name to its 'type' from the JSON."""
    return {d['name']: d.get('type', '') for d in data}


def _names_to_price_for_hdv(data: list, items: list, hdv: str) -> dict:
    """
    purpose:
        Collect every distinct name that must be OCR-priced when standing in
        front of a given HDV: the sheet items of that HDV type (for their
        "Prix") plus the recipe ingredients of that HDV type (for craft costs).
    input:
        data (list)  : full recipes JSON
        items (list) : item names read from the sheet
        hdv (str)    : "resource" | "equipment" | "consumable"
    output:
        dict: {name: 'sheet' | 'ingredient'} restricted to this HDV
    """
    type_of = _type_index(data)
    needed = {}

    # Sheet items whose own type belongs to this HDV -> priced for their "Prix"
    for name in items:
        if hdv_for_type(type_of.get(name, '')) == hdv:
            needed[name] = 'sheet'

    # Ingredients of this HDV type across every sheet item's recipe -> for "Coût"
    for name in items:
        for ing in parse_recipe_from_json(data, name):
            if hdv_for_type(ing.get('type', '')) == hdv:
                needed.setdefault(ing['name'], 'ingredient')

    return needed


def run_sync_hdv(hdv: str):
    """
    purpose:
        One-HDV workflow. Standing in front of the given HDV NPC, OCR-price
        every sheet item and every ingredient of that HDV type, cache the unit
        prices, write the "Prix" of the sheet items of this HDV, then recompute
        the "Coût" (+ "Recette") of every sheet item whose ingredients are all
        priced in the shared cache.
    input:
        hdv (str): "resource" | "equipment" | "consumable"
    """
    from utils.gsheet.gsheet import get_item_names, update_costs, update_prices

    data = _load_recipes_data()
    items = get_item_names()
    print(f"{len(items)} items read from the sheet.")

    cache = price_cache.load()
    needed = _names_to_price_for_hdv(data, items, hdv)
    print(f"HDV {hdv}: {len(needed)} item(s) to price.\n")

    for name in needed:
        sell, cost, suspicious = price_item(name, hdv)
        if suspicious:
            print(f"  {name}: {cost} Kamas  [!] suspicious -> skipped (not cached/written)")
            continue
        price_cache.set_price(cache, name, sell, cost)
        print(f"  {name}: prix {sell} / cout {cost} Kamas")
    price_cache.save(cache)

    # Write the "Prix" (cheapest per-unit) of the sheet items of this HDV
    type_of = _type_index(data)
    prices = {}
    for name in items:
        if hdv_for_type(type_of.get(name, '')) == hdv:
            p = price_cache.get_sell(cache, name)
            if p:
                prices[name] = p
    if prices:
        n = update_prices(prices)
        print(f"\n{n} price(s) written to the 'Prix' column.")

    # Recompute the "Coût" (max per-unit ingredients) of any fully priced item
    costs = {}
    recipes = {}
    for name in items:
        parsed_recipe = parse_recipe_from_json(data, name)
        if not parsed_recipe:
            continue
        complete = True
        for ing in parsed_recipe:
            unit = price_cache.get_cost(cache, ing['name'])
            if not unit:
                complete = False
                break
            ing['unit_cost'] = unit
        if complete:
            costs[name] = sum(r['quantity'] * r['unit_cost'] for r in parsed_recipe)
            recipes[name] = format_recipe_detail(parsed_recipe)

    if costs:
        n = update_costs(costs, recipes)
        print(f"{n} cost(s) written to the 'Coût' column.")


def main():
    # HDV workflows from the CLI (--resource / --equipment / --consumable)
    for flag, hdv in (
        ("--resource", "resource"),
        ("--equipment", "equipment"),
        ("--consumable", "consumable"),
    ):
        if flag in sys.argv:
            run_sync_hdv(hdv)
            ending_message()
            return

    # Pop the GUI to select items / HDV
    target_lst = create_window()

    # One button per HDV in the GUI
    if target_lst == "__SYNC_RESOURCE__":
        run_sync_hdv("resource")
        ending_message()
        return

    if target_lst == "__SYNC_EQUIPMENT__":
        run_sync_hdv("equipment")
        ending_message()
        return

    if target_lst == "__SYNC_CONSUMABLE__":
        run_sync_hdv("consumable")
        ending_message()
        return

    # Load JSON data from file
    recipe_file_path = "equipment_recipes.json"
    with files("dofus_cookbot.res").joinpath(recipe_file_path).open(encoding="utf-8") as f:
            data = json.loads(f.read())

    for target in target_lst:
        parsed_recipe = parse_recipe_from_json(data, target)
        if not parsed_recipe:
            print("No recipe found. Exiting...")
            sys.exit(1)
        
        for resource in parsed_recipe:
            item_name = resource['name']
            item_quantity = resource['quantity']
            item_type = resource['type']
            item_lvl = resource['level']

            price_info = determine_price(item_name, item_quantity, item_type, item_lvl)
            resource.update(price_info)

        # Create table report for the item
        create_report(target, parsed_recipe)

    ending_message()

if __name__ == "__main__":  
    main()