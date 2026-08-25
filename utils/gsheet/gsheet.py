##########
# Description: Google Sheets connector for Dofus Price Bot.
#              Reads the item list and writes the computed craft cost back
#              into the "Cout" column.
#
# Auth: OAuth 2.0 "Desktop app" client (NO service-account key needed, so it
#       works even when the org blocks iam.disableServiceAccountKeyCreation).
#
# Setup:
#   1. Google Cloud Console -> enable "Google Sheets API"
#   2. OAuth consent screen -> External + add yourself as Test user
#   3. Credentials -> OAuth client ID -> Desktop app -> download JSON
#   4. Save it as: utils/gsheet/credentials.json
#
# First run opens a browser to authorize; a token is cached in
# utils/gsheet/token.json for subsequent runs.
##########

import csv
import io
import os
import urllib.request
from datetime import datetime

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Read + write access to spreadsheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Your spreadsheet
SPREADSHEET_ID = "1VL7916sjzDG5n_yT75eA94y4L9m65YrhpMqEf5FlELI"

# Column headers (must match the first row of the sheet)
COL_ITEM = "Nom de l'item"
COL_COST = "Coût"
COL_DATE = "Date Coût"

_HERE = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(_HERE, "credentials.json")
TOKEN_PATH = os.path.join(_HERE, "token.json")


def _get_client() -> gspread.Client:
    """Authenticate via OAuth and return an authorized gspread client."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"Missing OAuth credentials file: {CREDENTIALS_PATH}\n"
                    "Follow the setup steps in the header of this file."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        # Cache the token for next time
        with open(TOKEN_PATH, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return gspread.authorize(creds)


def _get_worksheet(client: gspread.Client = None):
    """Return the first worksheet of the configured spreadsheet."""
    if client is None:
        client = _get_client()
    return client.open_by_key(SPREADSHEET_ID).sheet1


def get_item_names() -> list[str]:
    """
    purpose:
        Read the list of item names from the "Nom de l'item" column.
    output:
        list[str]: non-empty item names, in sheet order.
    """
    ws = _get_worksheet()
    records = ws.get_all_records()  # list of dicts keyed by header row
    names = [str(r.get(COL_ITEM, "")).strip() for r in records]
    return [n for n in names if n]


def get_item_names_public() -> list[str]:
    """
    purpose:
        Read item names WITHOUT authentication, using the public CSV export.
        Works only if the sheet is shared as "anyone with the link". Handy for
        a quick read when OAuth credentials are not set up yet.
    output:
        list[str]: non-empty item names, in sheet order.
    """
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"
    data = urllib.request.urlopen(url).read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(data))
    names = [str(row.get(COL_ITEM, "")).strip() for row in reader]
    return [n for n in names if n]


def update_item_names(renames: dict[str, str]) -> int:
    """
    purpose:
        Rename item cells in the "Nom de l'item" column, matching current
        values exactly.
    input:
        renames (dict): {current_name: corrected_name}
    output:
        int: number of cells renamed.
    """
    ws = _get_worksheet()

    header = ws.row_values(1)
    try:
        item_col = header.index(COL_ITEM) + 1
    except ValueError as e:
        raise ValueError(
            f"Could not find item column in the sheet header: {header}"
        ) from e

    item_names = ws.col_values(item_col)  # includes header at index 0

    updates = []
    for row_idx, name in enumerate(item_names[1:], start=2):  # skip header
        name = (name or "").strip()
        if name in renames:
            updates.append(
                {
                    "range": gspread.utils.rowcol_to_a1(row_idx, item_col),
                    "values": [[renames[name]]],
                }
            )

    if updates:
        ws.batch_update(updates)

    return len(updates)


def update_costs(costs: dict[str, int]) -> int:
    """
    purpose:
        Write craft costs back into the "Coût" column, matching rows by item name.
    input:
        costs (dict): {item_name: cost}
    output:
        int: number of rows updated.
    """
    ws = _get_worksheet()

    header = ws.row_values(1)
    try:
        item_col = header.index(COL_ITEM) + 1
        cost_col = header.index(COL_COST) + 1
    except ValueError as e:
        raise ValueError(
            f"Could not find required columns in the sheet header: {header}"
        ) from e

    # Optional "Date" column: written only if present in the sheet header
    date_col = header.index(COL_DATE) + 1 if COL_DATE in header else None
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    item_names = ws.col_values(item_col)  # includes header at index 0

    updates = []
    updated = 0
    for row_idx, name in enumerate(item_names[1:], start=2):  # skip header
        name = (name or "").strip()
        if name in costs:
            updated += 1
            updates.append(
                {
                    "range": gspread.utils.rowcol_to_a1(row_idx, cost_col),
                    "values": [[costs[name]]],
                }
            )
            if date_col:
                updates.append(
                    {
                        "range": gspread.utils.rowcol_to_a1(row_idx, date_col),
                        "values": [[today]],
                    }
                )

    if updates:
        ws.batch_update(updates)

    return updated


if __name__ == "__main__":
    # Quick manual test
    print("Reading item names...")
    items = get_item_names()
    print(f"Found {len(items)} items:")
    for it in items:
        print(f"  - {it}")
