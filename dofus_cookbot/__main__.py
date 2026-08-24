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

    def _to_int(digits: str) -> int:
        digits = ''.join(filter(str.isdigit, digits))
        return int(digits) if digits else 0

    try:
        # Preprocess: grayscale + upscale x3 greatly improves OCR accuracy
        gray = screenshot.convert("L")
        gray = gray.resize((gray.width * 3, gray.height * 3))
        text = pytesseract.image_to_string(gray, config="--psm 6")

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
        return result

    except Exception as e:
        print(f"Error with OCR recognition: {e}")
        return {'price': 1, 'price_10': 0, 'price_100': 0}


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

    print(
        f"Prices found for {item_name}: "
        f"x1={prices['price']} | x10={prices['price_10']} | x100={prices['price_100']} Kamas"
    )

    return {
        'price': prices['price'],
        'price_10': prices['price_10'],
        'price_100': prices['price_100'],
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
                            'type': ingredient_info['type'],
                            'quantity': int(ingredient_info['quantity']),
                            'level': int(ingredient_info['lvl'])
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
    table.field_names = [target, "Level", "Quantity", "Price x1", "Price x10", "Price x100", "Total (x1)"]
    total_price_all_items = 0 

    try:
        for resource in parsed_recipe:
            item_name = resource['name']
            item_lvl = resource['level']
            item_quantity = resource['quantity']
            item_price = resource['price']
            item_price_10 = resource.get('price_10', 0)
            item_price_100 = resource.get('price_100', 0)

            total_price = item_quantity * item_price
            total_price_all_items += total_price

            table.add_row([item_name, item_lvl, item_quantity, item_price, item_price_10, item_price_100, total_price])

        # Add 20% tax
        tax = round(total_price_all_items * 0.20)
        total_price_with_tax = total_price_all_items + tax

        # Print total price with tax
        table.add_row(["-" * 10, "-" * 10, "-" * 10, "-" * 10, "-" * 10, "-" * 10, "-" * 10])
        table.add_row(["Total Price (w/ taxes)", "", "", "", "", "", total_price_with_tax])

        print(table)
    
    except TypeError:
        print("Error when calculating price")
    except Exception as e:
        print(f"Error when creating report: {e}")

def main():
    # Pop the GUI to select items
    target_lst = create_window()

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