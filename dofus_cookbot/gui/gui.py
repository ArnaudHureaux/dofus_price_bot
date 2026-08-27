##########
# Author: wildpasta
# Description: GUI module that create the window for item selection
##########

# Standard library imports
import json
import sys
from importlib.resources import files

# Third party imports
try:
    from tkinter import ACTIVE, END
    from tkinter import Label, Listbox, messagebox, Tk, ttk
except ModuleNotFoundError as e:
    print(f"ModuleNotFoundError: {e}")
    print("Please install the required modules using the following command:")
    print("pip install -r requirements.txt")
    sys.exit(1)

def get_item_names(recipe_file_path: str) -> list[str]:
    """ 
    purpose:
        load the recipes from a JSON file
    input:
        recipe_file_path (str): the path of the JSON file
    output:
        names (list[str]): The list of recipe names
    """

    try:
        with files("dofus_cookbot.res").joinpath(recipe_file_path).open(encoding="utf-8") as f:
            data = json.loads(f.read())
        names = [recipe['name'] for recipe in data]
        names.sort()
        
        return names
    
    except FileNotFoundError as e:
        print(f"FileNotFoundError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Exception: {e}")
        sys.exit(1)

def create_window():
    item_requested = list()
    action = {"hdv": None}
    root = Tk()
    root.title("Dofus Cooker")
    root.geometry("600x600")
    root.config(bg='#DFE7F2')
    style = ttk.Style(root)
    style.theme_use('clam')

    def on_sync_resource_click():
        action["hdv"] = "resource"
        root.destroy()

    def on_sync_equipment_click():
        action["hdv"] = "equipment"
        root.destroy()

    def on_sync_consumable_click():
        action["hdv"] = "consumable"
        root.destroy()

    # Update the listbox
    def update(data):
        # Clear the listbox
        global_item_list.delete(0, END)

        # Add items to our listbox
        for item in data:
            global_item_list.insert(END, item)

    # Update entry box with listbox clicked
    def fillout(event):
        # Delete entrybox content
        my_entry.delete(0, END)

        # Add clicked list item to entry box
        my_entry.insert(0, global_item_list.get(ACTIVE))

    # create function to check entry vs listbox
    def check(event):
        # grab what is typed
        typed = my_entry.get()
        if typed == '':
            data = items
        else:
            data = list()
            for item in items:
                if typed.lower() in item.lower():
                    data.append(item)
        update(data)

    my_label = Label(root, text="Start typing...", font=("Helvetica", 14), fg="black")
    my_label.pack(pady=20)

    my_entry = ttk.Entry(root, font=("Helvetica", 20))
    my_entry.pack()

    global_item_list = Listbox(root, width=50)
    global_item_list.pack(pady=40)

    sync_resource_button = ttk.Button(root, text="SYNC HDV RESSOURCE", command=on_sync_resource_click)
    sync_resource_button.pack(pady=10)

    sync_equipment_button = ttk.Button(root, text="SYNC HDV \u00c9QUIPEMENT", command=on_sync_equipment_click)
    sync_equipment_button.pack(pady=10)

    sync_consumable_button = ttk.Button(root, text="SYNC HDV CONSOMMABLE", command=on_sync_consumable_click)
    sync_consumable_button.pack(pady=10)

    recipe_file_path = "equipment_recipes.json"
    items = get_item_names(recipe_file_path)

    try:
        # Add the items to our list
        update(items)

        # Bind the listbox on click
        global_item_list.bind("<<ListboxSelect>>", fillout)

        # Create a binding on the entry box
        my_entry.bind("<KeyRelease>", check)
    except Exception as e:
        print(f"Error in GUI display: {e}")

    root.mainloop()

    if action["hdv"] == "resource":
        return "__SYNC_RESOURCE__"
    if action["hdv"] == "equipment":
        return "__SYNC_EQUIPMENT__"
    if action["hdv"] == "consumable":
        return "__SYNC_CONSUMABLE__"
    return item_requested

def ending_message():
    messagebox.showinfo("Finished", "The search has finished!")

def main() -> None:
    create_window()
    ending_message()

if __name__ == "__main__":
    sys.exit(main())