"""Anomaly detection pipeline.

The modules here (``main``, ``app``, ``tests``) import their helpers as
``from src.validate import ...`` — i.e. they expect this directory itself to be
on ``sys.path``, which is true when they are run as scripts from inside the
folder::

    python main.py
    streamlit run app.py

Appending that directory here means the same imports also resolve when the
package is imported from the repo root::

    from anomaly_detection.main import run_pipeline

so the pipeline can be called as a library without changing a single import in
the modules themselves. ``append`` rather than ``insert(0)`` so this directory's
generic module names (``main``, ``src``) never shadow anything already
importable — notably the repo's own ``backend/main.py``.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.append(_HERE)
