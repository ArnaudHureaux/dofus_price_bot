# Makefile - Dofus Price Bot
# Short, memorable targets (<= 6 chars). Run with: make <target>

PY := .venv/Scripts/python.exe

.PHONY: help run pos pick shot cap grab clean

# help  : list available commands
help:
	@echo "Dofus Price Bot - commands"
	@echo "  make run    -> launch the bot (GUI + autoclick + OCR)"
	@echo "  make pos    -> live mouse position finder"
	@echo "  make pick   -> visual region selector (draw a box -> bbox + OCR)"
	@echo "  make shot   -> full-screen capture (6s delay) into capture_full.png"
	@echo "  make clean  -> remove generated screenshots"

# run   : start the bot
run:
	$(PY) -m dofus_cookbot

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
