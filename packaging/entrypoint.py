"""PyInstaller's Analysis needs a top-level script outside the src/ package
layout - this just delegates straight to the real entry point.
"""

from trakt_calendar_sync.main import main

if __name__ == "__main__":
    main()
