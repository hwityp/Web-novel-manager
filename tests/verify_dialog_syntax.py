import sys
import os
sys.path.append(os.getcwd())

print("Checking syntax of gui/genre_confirm_dialog.py...")
try:
    import gui.genre_confirm_dialog
    print("Import Successful! Syntax is valid.")
except Exception as e:
    print(f"Import Failed: {e}")
    import traceback
    traceback.print_exc()
