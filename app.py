"""
ICU Guard v5.0 — Application Root Entry Point
Launches the NiceGUI Clinical Decision Support Dashboard.
"""

from dashboard.app import main

if __name__ in {"__main__", "__mp_main__"}:
    main()
