"""Glue between the four modules.

Nothing here holds data of its own. The generated rental history is the single
source of truth and everything in this package is a *projection* of it, which is
the only reason the dashboard, the forecast page and the anomaly page can be
trusted to describe the same fleet.
"""
