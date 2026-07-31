import pandas as pd
from datetime import datetime

def parse_date(date_str):
    """Safely parses a YYYY-MM-DD date string. Returns a datetime.date object or None."""
    if not date_str or pd.isna(date_str) or str(date_str).strip() in ["", "NULL", "nan", "None"]:
        return None
    try:
        return datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
    except Exception:
        return None

def parse_float(val):
    """Safely parses a float value. Returns 0.0 if empty or NULL."""
    if not val or pd.isna(val) or str(val).strip() in ["", "NULL", "nan", "None"]:
        return 0.0
    try:
        return float(str(val).strip())
    except ValueError:
        return 0.0

def parse_int_or_none(val):
    """Safely parses an integer or returns None if empty or NULL."""
    if not val or pd.isna(val) or str(val).strip() in ["", "NULL", "nan", "None"]:
        return None
    try:
        return int(float(str(val).strip()))
    except ValueError:
        return None

def validate_records(df, simulated_current_date):
    """
    Performs data integrity checks on all rows of the DataFrame.
    Returns:
        invalid_indices (set): Indices (0-indexed) that failed validation.
        flags_dict (dict): Map of row index to list of reason traces.
    """
    if isinstance(simulated_current_date, str):
        simulated_current_date = datetime.strptime(simulated_current_date, "%Y-%m-%d").date()

    invalid_indices = set()
    flags_dict = {i: [] for i in range(len(df))}

    # Prepare validated dates and floats
    parsed_in = df["Check_In_Date"].apply(parse_date)
    parsed_out = df["Check_Out_Date"].apply(parse_date)
    engine_hours = df["Engine_Hours_Day"].apply(parse_float)
    idle_hours = df["Idle_Hours_Day"].apply(parse_float)
    rental_days = df["Rental_Days"].apply(parse_int_or_none)

    # 1. Impossible hours
    for idx in range(len(df)):
        eng = engine_hours.iloc[idx]
        idl = idle_hours.iloc[idx]
        total = eng + idl
        if total > 24.0:
            flags_dict[idx].append({
                "rule": "impossible_hours",
                "engine_hours": eng,
                "idle_hours": idl,
                "total_hours": total,
                "threshold": 24.0
            })
            invalid_indices.add(idx)

    # 2. Bad date order
    for idx in range(len(df)):
        chk_in = parsed_in.iloc[idx]
        chk_out = parsed_out.iloc[idx]
        if chk_in and chk_out and chk_out < chk_in:
            flags_dict[idx].append({
                "rule": "bad_date_order",
                "check_in": str(chk_in),
                "check_out": str(chk_out),
                "reason": "checkout_before_checkin"
            })
            invalid_indices.add(idx)

    # 3. Zero-activity row
    for idx in range(len(df)):
        eng = engine_hours.iloc[idx]
        idl = idle_hours.iloc[idx]
        if eng == 0.0 and idl == 0.0:
            flags_dict[idx].append({
                "rule": "zero_activity",
                "engine_hours": eng,
                "idle_hours": idl
            })
            invalid_indices.add(idx)

    # 5. Rental-days mismatch
    for idx in range(len(df)):
        chk_in = parsed_in.iloc[idx]
        chk_out = parsed_out.iloc[idx]
        r_days = rental_days.iloc[idx]
        if chk_in and chk_out and pd.notna(r_days):
            actual_days = (chk_out - chk_in).days
            stated_days = int(float(r_days))
            if abs(actual_days - stated_days) != 0:
                flags_dict[idx].append({
                    "rule": "rental_days_mismatch",
                    "stated_days": stated_days,
                    "actual_days": actual_days,
                    "difference": abs(actual_days - stated_days)
                })
                invalid_indices.add(idx)

    # 4. Booking conflict (overlapping rental intervals for the same Equipment_ID)
    #
    # This used to compare every row against every other row, skipping the pair
    # unless the Equipment_IDs matched — so the work was O(n^2) while the answer
    # only ever depended on rows sharing an Equipment_ID. Bucketing by
    # Equipment_ID first is identical in behaviour, including the order flags
    # are appended in, because candidate rows are still walked in ascending
    # index order.
    #
    # It only matters at scale: on the 76-row sample the difference is
    # invisible, but on the 7,209-row fleet history the old form is ~52M
    # iterations of scalar .iloc lookups (about four minutes) against ~76k here.
    ids = [str(value).strip() for value in df["Equipment_ID"]]

    rows_by_equipment = {}
    for idx, equipment_id in enumerate(ids):
        rows_by_equipment.setdefault(equipment_id, []).append(idx)

    # Materialise the parsed date columns once. Scalar .iloc access inside the
    # nested loop was a large part of the original cost.
    starts = list(parsed_in)
    ends = list(parsed_out)

    for i in range(len(df)):
        in1 = starts[i]
        if not in1:
            continue
        out1 = ends[i] or simulated_current_date

        if ends[i] and ends[i] < in1:
            continue

        for j in rows_by_equipment[ids[i]]:
            if i == j:
                continue

            in2 = starts[j]
            if not in2:
                continue
            out2 = ends[j] or simulated_current_date

            if ends[j] and ends[j] < in2:
                continue

            if in1 <= out2 and in2 <= out1:
                flags_dict[i].append({
                    "rule": "booking_conflict",
                    "conflicting_row_index": j + 2,
                    "conflicting_equipment": ids[j],
                    "interval_1": f"{in1} to {out1}",
                    "interval_2": f"{in2} to {out2}"
                })
                invalid_indices.add(i)

    return invalid_indices, flags_dict
