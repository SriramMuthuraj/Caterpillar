import pandas as pd

def compute_severity_and_consolidate(df, validation_flags, asset_flags, baseline_flags, group_flags):
    """
    Combines flags from all modules into a single consolidated result per row.
    Computes a composite score:
      - Validation flags (integrity errors) -> 3 points each
      - Asset rule flags -> 2 points each
      - Self-baseline flags -> 3 points each
      - Group analysis flags -> 3 points each
    Determines severity level:
      - Critical: score >= 6
      - Warning: score >= 3
      - Normal: score < 3
    Returns:
        results (list): A list of dictionaries representing the consolidated result for each row.
    """
    results = []

    for idx in range(len(df)):
        row = df.iloc[idx]
        
        # Get flags for this row from all sources
        row_validation = validation_flags.get(idx, [])
        row_asset = asset_flags.get(idx, [])
        row_baseline = baseline_flags.get(idx, [])
        row_group = group_flags.get(idx, [])

        # Combine all flags
        row_all_flags = row_validation + row_asset + row_baseline + row_group

        # Compute composite score
        score = (
            (len(row_validation) * 3) + 
            (len(row_asset) * 2) + 
            (len(row_baseline) * 3) + 
            (len(row_group) * 3)
        )

        # Map to severity level
        if score >= 6:
            level = "Critical"
        elif score >= 3:
            level = "Warning"
        else:
            level = "Normal"

        # Build consolidated result dict
        res = {
            "row_index": idx + 2, # 1-based index (accounting for header as row 1)
            "Equipment_ID": str(row["Equipment_ID"]).strip(),
            "Type": str(row["Type"]).strip(),
            "Site_ID": str(row["Site_ID"]).strip(),
            "Check_In_Date": str(row["Check_In_Date"]).strip() if pd.notna(row["Check_In_Date"]) else "",
            "Check_Out_Date": str(row["Check_Out_Date"]).strip() if pd.notna(row["Check_Out_Date"]) else "",
            "Engine_Hours_Day": float(row["Engine_Hours_Day"]),
            "Idle_Hours_Day": float(row["Idle_Hours_Day"]),
            "Rental_Days": str(row["Rental_Days"]).strip() if pd.notna(row["Rental_Days"]) else "",
            "Last_Operator_ID": str(row["Last_Operator_ID"]).strip(),
            "score": score,
            "level": level,
            "flags": row_all_flags
        }
        
        results.append(res)

    return results
