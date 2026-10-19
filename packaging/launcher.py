"""Entry point for the frozen Windows build.

PyInstaller cannot run a package's ``__main__`` directly. A windowed build also
has no console, so ``sys.stdout``/``sys.stderr`` are ``None``; give them a sink so
``--version`` and logging cannot crash the app.
"""

import os
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")  # noqa: SIM115
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")  # noqa: SIM115

from pinganillo.__main__ import main

raise SystemExit(main())
