##########
# Author: wildpasta
# Description: GUI module that create the window for item selection
##########

# Standard library imports
import sys

# Third party imports
try:
    from tkinter import messagebox, Tk, ttk
except ModuleNotFoundError as e:
    print(f"ModuleNotFoundError: {e}")
    print("Please install the required modules using the following command:")
    print("pip install -r requirements.txt")
    sys.exit(1)


def create_window():
    action = {"hdv": None}
    root = Tk()
    root.title("Dofus Cooker")
    root.geometry("300x240")
    root.config(bg='#DFE7F2')
    style = ttk.Style(root)
    style.theme_use('clam')

    def _pick(hdv):
        def handler():
            action["hdv"] = hdv
            root.destroy()
        return handler

    ttk.Button(root, text="SYNC (tous les HDV)", command=_pick("all")).pack(pady=(20, 12), padx=20, fill="x")
    ttk.Button(root, text="SYNC HDV \u00c9QUIPEMENT", command=_pick("equipment")).pack(pady=6, padx=20, fill="x")
    ttk.Button(root, text="SYNC HDV RESSOURCE", command=_pick("resource")).pack(pady=6, padx=20, fill="x")
    ttk.Button(root, text="SYNC HDV CONSOMMABLE", command=_pick("consumable")).pack(pady=6, padx=20, fill="x")

    root.mainloop()

    return {
        "all": "__SYNC_ALL__",
        "equipment": "__SYNC_EQUIPMENT__",
        "resource": "__SYNC_RESOURCE__",
        "consumable": "__SYNC_CONSUMABLE__",
    }.get(action["hdv"], [])

def ending_message():
    messagebox.showinfo("Finished", "The search has finished!")

def main() -> None:
    create_window()
    ending_message()

if __name__ == "__main__":
    sys.exit(main())