"""MOD-11 Forecast Engine (FR-6).

Weekly demand per (equipment_type x site), with prediction intervals earned from
a rolling-origin backtest and an explicit ``insufficient_data`` verdict where the
history is too thin to support a number.

Public surface::

    from backend.forecast import service
    service.warm()                                  # startup, NFR-2
    service.get_forecast(type="Excavator", site="S002")
    service.get_backtest()
    service.demand_table()                          # for MOD-12 / MOD-14

    from backend.forecast.api import router

Submodules are imported explicitly rather than re-exported here, so importing
the package does not drag in scikit-learn before it is needed.
"""

__all__ = [
    "api",
    "backtest",
    "calibration",
    "clock_adapter",
    "config",
    "features",
    "history",
    "model",
    "service",
]
