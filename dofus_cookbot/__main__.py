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

    import numpy as np

    def _to_int(digits: str) -> int:
        digits = ''.join(filter(str.isdigit, digits))
        return int(digits) if digits else 0

    try:
        # Preprocess: keep only the white price text and drop everything else
        # (notably the colored kamas icon, which the OCR otherwise reads as an
        # extra trailing digit). White text = bright + low saturation.
        arr = np.array(screenshot.convert("RGB")).astype(int)
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        brightness = (r + g + b) / 3
        saturation = (
            np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
        )
        text_mask = (brightness > 140) & (saturation < 40)
        binary = np.where(text_mask, 0, 255).astype("uint8")  # black text on white
        clean = Image.fromarray(binary)
        clean = clean.resize((clean.width * 4, clean.height * 4))
        text = pytesseract.image_to_string(
            clean, config="--psm 6 -c tessedit_char_whitelist=0123456789 "
        )

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
        Sanity-check OCR-read prices. In Dofus the per-unit cost of a bigger
        lot is usually close to (and never wildly cheaper than) the smaller
        lot's unit price. A common OCR glitch is the kamas icon being read as
        an extra trailing digit (e.g. 179999 -> 1799994).
    input:
        prices (dict): {'price': int, 'price_10': int, 'price_100': int}
    output:
        bool: True if the prices look inconsistent (suspicious), else False.
    """

    p1 = prices.get('price', 0) or 0
    p10 = prices.get('price_10', 0) or 0
    p100 = prices.get('price_100', 0) or 0

    # Unit price could not be read
    if p1 <= 1:
        return True

    # Per-unit cost of each available lot; should stay within a sane ratio
    unit_costs = [p1]
    if p10:
        unit_costs.append(p10 / 10)
    if p100:
        unit_costs.append(p100 / 100)

    lo, hi = min(unit_costs), max(unit_costs)
    # If the cheapest and most expensive per-unit costs differ by more than
    # a factor of 3, an OCR misread is very likely.
    if lo > 0 and hi / lo > 3:
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

    # click: clear research
    do_click(881, 378)
    sleep(0.4)

    # click: searchbar
    do_click(759, 379)
    sleep(0.2)

    # keyboard: write the item name in searchbar
    keyboard.type(item_name)
    sleep(0.7)

    # click: first item to unwrap prices
    do_click(1225, 451)
    sleep(1)

    # Screenshot the whole Lot/Prix panel (left side of the screen).
    # Coordinates calibrated with utils/pos_finder/region_selector.py.
    # pyautogui is used (reliable) instead of pyscreenshot.
    # region = (left, top, width, height)
    panel = pyautogui.screenshot(region=(111, 259, 616 - 111, 627 - 259))
    prices = process_image(panel, item_name)
    item_current_price = prices['price']

    warn = "  [!] suspicious OCR" if prices.get('suspicious') else ""
    print(
        f"Prices found for {item_name}: "
        f"x1={prices['price']} | x10={prices['price_10']} | x100={prices['price_100']} Kamas{warn}"
    )

    return {
        'price': prices['price'],
        'price_10': prices['price_10'],
        'price_100': prices['price_100'],
        'suspicious': prices.get('suspicious', False),
    }

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

def compute_cost_for_target(data: list, target: str) -> tuple:
    """
    purpose:
        Compute the craft cost of one target item by pricing each ingredient
        in the HDV via OCR.
    input:
        data (list)  : full recipes JSON
        target (str) : item name to craft
    output:
        tuple: (total_cost:int, parsed_recipe:list) or (None, None) if no recipe
    """
    parsed_recipe = parse_recipe_from_json(data, target)
    if not parsed_recipe:
        return None, None

    for resource in parsed_recipe:
        price_info = determine_price(
            resource['name'], resource['quantity'], resource['type'], resource['level']
        )
        resource.update(price_info)
        resource['unit_cost'] = effective_unit_price(price_info)

    total_cost = sum(r['quantity'] * r['unit_cost'] for r in parsed_recipe)
    return total_cost, parsed_recipe


def run_sync():
    """
    purpose:
        Full workflow: read the item list from the Google Sheet, price each
        recipe in the HDV, then write the craft cost back to the "Coût" column.
    """
    from utils.gsheet.gsheet import get_item_names, update_costs

    recipe_file_path = "equipment_recipes.json"
    with files("dofus_cookbot.res").joinpath(recipe_file_path).open(encoding="utf-8") as f:
        data = json.loads(f.read())

    items = get_item_names()
    print(f"{len(items)} items read from the sheet.\n")

    costs = {}
    for target in items:
        total_cost, parsed_recipe = compute_cost_for_target(data, target)
        if total_cost is None:
            print(f"[skip] no recipe found for: {target}")
            continue
        create_report(target, parsed_recipe)
        costs[target] = total_cost
        print(f"=> {target}: craft cost = {total_cost} Kamas\n")

    if costs:
        n = update_costs(costs)
        print(f"{n} cost(s) written to the 'Coût' column of the sheet.")
    else:
        print("No cost computed, nothing written.")


def main():
    # --sync: headless workflow driven by the Google Sheet
    if "--sync" in sys.argv:
        run_sync()
        ending_message()
        return

    # Pop the GUI to select items
    target_lst = create_window()

    # SYNC button pressed in the GUI -> run the full sheet workflow
    if target_lst == "__SYNC__":
        run_sync()
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