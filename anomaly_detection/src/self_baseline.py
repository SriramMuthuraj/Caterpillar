import pandas as pd
import numpy as np

def check_self_baseline(valid_df):
    """
    For a given Equipment_ID with 2+ historical rows (prior chronologically),
    flags if current Engine_Hours_Day deviates more than 2 standard deviations
    from that equipment's historical mean.
    Returns:
        flags_dict (dict): Map of row index to a list of flag details.
    """
    flags_dict = {}

    for idx, row in valid_df.iterrows():
        eq_id = str(row["Equipment_ID"]).strip()
        curr_in = row["parsed_in"]
        curr_val = float(row["Engine_Hours_Day"])

        if not curr_in:
            continue

        # Get historical rows: rows for same equipment with parsed_in strictly earlier than current row
        hist_rows = valid_df[(valid_df["Equipment_ID"] == eq_id) & (valid_df["parsed_in"] < curr_in)]

        if len(hist_rows) >= 2:
            hist_vals = hist_rows["Engine_Hours_Day"].values.astype(float)
            mean_val = np.mean(hist_vals)
            std_val = np.std(hist_vals, ddof=1)

            # Handle zero variance safely
            effective_std = 1e-6 if std_val == 0.0 else std_val
            dev_std = abs(curr_val - mean_val) / effective_std

            if dev_std > 2.0:
                flags_dict[idx] = [{
                    "rule": "self_baseline_deviation",
                    "engine_hours": curr_val,
                    "historical_mean": round(mean_val, 4),
                    "historical_std": round(std_val, 4),
                    "deviation_stdevs": round(dev_std, 4),
                    "threshold_stdevs": 2.0,
                    "historical_count": len(hist_vals)
                }]

    return flags_dict
