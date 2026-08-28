# Makefile - Dofus Price Bot
# Short, memorable targets (<= 6 chars). Run with: make <target>

PY := .venv/Scripts/python.exe

.PHONY: help run sync res equ conso reco recof dash pos pick shot clean

# help  : list available commands
help:
	@echo "Dofus Price Bot - commands"
	@echo "  make run    -> launch the bot (GUI: one button per HDV)"
	@echo "  make sync   -> full chain: equipement -> ressource -> consommable (with travel)"
	@echo "  make res    -> HDV Ressource: price resources -> write Prix + Cout"
	@echo "  make equ    -> HDV Equipement: price gear -> write Prix + Cout"
	@echo "  make conso  -> HDV Consommable: price consumables -> write Prix + Cout"
	@echo "  make reco   -> fetch missing recipes from the sheet via DofusDB API"
	@echo "  make recof  -> re-fetch + overwrite existing sheet recipes (fix Touch data)"
	@echo "  make dash   -> recompute Stats + Dashboard from the Historic tab"
	@echo "  make pos    -> live mouse position finder"
	@echo "  make pick   -> visual region selector (draw a box -> bbox + OCR)"
	@echo "  make shot   -> full-screen capture (6s delay) into capture_full.png"
	@echo "  make clean  -> remove generated screenshots"

# run   : start the bot
run:
	$(PY) -m dofus_cookbot

# sync  : full chain across the 3 HDV with map travel (needs calibrated coords)
sync:
	$(PY) -m dofus_cookbot --sync

# res   : HDV Ressource workflow
res:
	$(PY) -m dofus_cookbot --resource

# equ   : HDV Equipement workflow
equ:
	$(PY) -m dofus_cookbot --equipment

# conso : HDV Consommable workflow
conso:
	$(PY) -m dofus_cookbot --consumable

# reco  : fetch missing recipes from the sheet via DofusDB API
reco:
	$(PY) utils/api/fetch_recipes.py

# recof : re-fetch AND overwrite existing sheet recipes (fixes wrong Touch data)
recof:
	$(PY) utils/api/fetch_recipes.py --refresh

# dash  : recompute Stats + Dashboard from the Historic tab (no scraping)
dash:
	$(PY) -m dofus_cookbot --dashboard

# pos   : live cursor position
pos:
	$(PY) utils/pos_finder/position_finder.py

# pick  : draw a rectangle to get coordinates + OCR
pick:
	$(PY) utils/pos_finder/region_selector.py

# shot  : capture the whole screen to calibrate
shot:
	$(PY) utils/pos_finder/test_capture.py

# clean : delete generated capture images
clean:
	-del /Q capture_full.png capture_test.png 2>nul
