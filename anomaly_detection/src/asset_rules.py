import pandas as pd
from datetime import datetime

# Configuration Constants
SIMULATED_CURRENT_DATE = datetime(2025, 6, 15).date()
OVERDUE_THRESHOLD_DAYS = 20

def check_asset_rules(valid_df, simulated_current_date=SIMULATED_CURRENT_DATE, overdue_threshold_days=OVERDUE_THRESHOLD_DAYS):
    """
    Runs basic asset rules on valid rows.
    Returns a dictionary mapping original row index to a list of flag details dicts.
    """
    if isinstance(simulated_current_date, str):
        simulated_current_date = datetime.strptime(simulated_current_date, "%Y-%m-%d").date()

    flags_dict = {}

    for idx, row in valid_df.iterrows():
        row_flags = []
        
        # Parse fields
        site_id = str(row["Site_ID"]).strip()
        op_id = str(row["Last_Operator_ID"]).strip()
        eng = float(row["Engine_Hours_Day"])
        idl = float(row["Idle_Hours_Day"])
        
        # 6. Unassigned equipment
        if site_id == "NULL":
            row_flags.append({
                "rule": "unassigned_equipment",
                "value": site_id,
                "threshold": "non-NULL"
            })
            
        # 7. No accountability
        if op_id == "NULL":
            row_flags.append({
                "rule": "no_accountability",
                "value": op_id,
                "threshold": "non-NULL"
            })
            
        # 8. Under-utilization
        idle_ratio = idl / max(eng + idl, 1.0)
        if idle_ratio > 0.75:
            row_flags.append({
                "rule": "under_utilized",
                "idle_ratio": round(idle_ratio, 4),
                "threshold": 0.75
            })
            
        # 9. Overdue (no Check_Out_Date present)
        # Check if parsed Check_Out_Date (parsed_out) is None/missing
        chk_out = row.get("parsed_out")
        chk_in = row.get("parsed_in")
        
        # If parsed_out is None, it means the check-out date is missing (active rental)
        if not chk_out and chk_in:
            days_active = (simulated_current_date - chk_in).days
            if days_active > overdue_threshold_days:
                row_flags.append({
                    "rule": "overdue",
                    "days_active": days_active,
                    "threshold_days": overdue_threshold_days,
                    "check_in_date": str(chk_in)
                })

        if row_flags:
            flags_dict[idx] = row_flags

    return flags_dict
