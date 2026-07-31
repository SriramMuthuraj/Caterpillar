# ==============================================================================
# EDGE CASES HANDLED IN THIS PIPELINE:
# 1. Group with fewer than 3 members -> skip comparison, no false signal
#    - Handled in src/group_analysis.py: 'analyze_group_imbalance' checks
#      if the number of rows in the group is >= 3.
# 2. All group members near-identical (no real variance) -> minimum deviation
#    threshold (20pp) prevents flagging pure noise
#    - Handled in src/group_analysis.py: a hard deviation threshold of 0.20
#      (20 percentage points) is enforced.
# 3. NULL Site_ID / Operator_ID rows excluded from group averages, handled
#    separately in Tier 1 instead
#    - Handled in src/group_analysis.py: 'analyze_group_imbalance' explicitly
#      filters out rows where Site_ID or Last_Operator_ID is "NULL" or "".
#      These rows are flagged separately by Tier 1 checks in src/asset_rules.py.
# 4. Integrity-failed rows excluded from every group/baseline average
#    - Handled in main.py & tests/test_fixtures.py: output of validate.py (invalid_indices)
#      is used to drop failed rows before passing the remainder (valid_df)
#      to asset_rules, self_baseline, and group_analysis.
# 5. New equipment with 0-1 historical rows -> self_baseline skips, falls
#    back to Tier 1 threshold rule only
#    - Handled in src/self_baseline.py: checks if the count of prior chronological
#      valid rows for the Equipment_ID is >= 2.
# 6. rental_days = 0 (same-day return) -> no division by zero anywhere
#    - Handled in validate.py (uses max(x, 1) or safe time diff) and
#      asset_rules.py (uses max(eng + idl, 1.0) for idle ratio denominator).
# 7. Multiple flags on one row -> composite score, not duplicate alerts
#    - Handled in src/severity.py: consolidates all validation, asset, baseline,
#      and group flags for a row into a single composite dictionary.
# 8. No Check_Out_Date present -> explicit SIMULATED_CURRENT_DATE handling,
#    documented as an assumption, not left ambiguous
#    - Handled in src/validate.py (for overlaps) and src/asset_rules.py
#      (for overdue rentals) using SIMULATED_CURRENT_DATE = 2025-06-15.
# ==============================================================================

import os
import sys
import argparse
import json
import pandas as pd
from datetime import datetime

from src.validate import validate_records
from src.asset_rules import check_asset_rules, SIMULATED_CURRENT_DATE, OVERDUE_THRESHOLD_DAYS
from src.self_baseline import check_self_baseline
from src.group_analysis import check_group_imbalances
from src.severity import compute_severity_and_consolidate

# src.explain imports google.genai at module level. Gemini is optional and OFF by
# default, so importing it here would make the whole pipeline unusable wherever
# google-genai is not installed. Imported lazily at the point of use instead.

def write_structured_outputs(results, output_dir):
    # Ensure directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate JSON
    json_data = []
    for r in results:
        # Convert flags to structured format
        mapped_flags = []
        for f in r.get("flags", []):
            rule = f.get("rule", "")
            
            # Map category
            if rule in {"impossible_hours", "bad_date_order", "zero_activity", "rental_days_mismatch", "booking_conflict"}:
                category = "integrity"
            elif rule in {"unassigned_equipment", "no_accountability", "under_utilized", "overdue"}:
                category = "asset_rule"
            elif rule == "self_baseline_deviation":
                category = "self_baseline"
            elif rule in {"type_level_imbalance", "site_id_level_imbalance", "last_operator_id_level_imbalance"}:
                category = "group"
            else:
                category = "unknown"
                
            # Formulate reason
            reason = ""
            if rule == "impossible_hours":
                reason = f"Impossible Hours (Total: {f.get('total_hours')}h)"
            elif rule == "bad_date_order":
                reason = "Bad Date Order (Checkout before checkin)"
            elif rule == "zero_activity":
                reason = "Zero-Activity Row"
            elif rule == "rental_days_mismatch":
                reason = f"Rental Days Mismatch (Stated: {f.get('stated_days')}, Actual: {f.get('actual_days')})"
            elif rule == "booking_conflict":
                reason = f"Booking Conflict (Conflicting Row: {f.get('conflicting_row_index')})"
            elif rule == "unassigned_equipment":
                reason = "Unassigned Equipment (Site is NULL)"
            elif rule == "no_accountability":
                reason = "No Accountability (Operator is NULL)"
            elif rule == "under_utilized":
                reason = f"Under-utilized (Idle ratio: {f.get('idle_ratio', 0.0):.2%})"
            elif rule == "overdue":
                reason = f"Overdue Active Rental ({f.get('days_active')} days active)"
            elif rule == "self_baseline_deviation":
                reason = f"Self-Baseline Deviation ({f.get('deviation_stdevs', 0.0):.2f} SD)"
            elif rule.endswith("_level_imbalance"):
                g_col = rule.replace("_level_imbalance", "").replace("id", "ID").replace("last_operator_", "Operator ").title()
                reason = f"{g_col} Imbalance (Idle ratio: {f.get('idle_ratio', 0.0):.2%}, Group avg: {f.get('group_average', 0.0):.2%})"
            else:
                reason = f"Unknown rule: {rule}"
                
            # Formulate details (excluding rule)
            details = {k: v for k, v in f.items() if k != "rule"}
            
            mapped_flags.append({
                "name": rule,
                "category": category,
                "reason": reason,
                "details": details
            })
            
        # Calculate idle ratio and validity
        eng = float(r.get("Engine_Hours_Day", 0.0))
        idl = float(r.get("Idle_Hours_Day", 0.0))
        total_hours = eng + idl
        idle_ratio = float(idl / total_hours) if total_hours > 0.0 else None
        
        is_valid_row = not any(f["category"] == "integrity" for f in mapped_flags)
        
        json_data.append({
            "row_id": int(r["row_index"]),
            "equipment_id": r["Equipment_ID"],
            "type": r["Type"],
            "site_id": r["Site_ID"],
            "operator_id": r["Last_Operator_ID"],
            "check_in": r["Check_In_Date"],
            "check_out": r["Check_Out_Date"],
            "idle_ratio": idle_ratio,
            "is_valid_row": is_valid_row,
            "score": int(r["score"]),
            "severity": r["level"],
            "flags": mapped_flags
        })
        
    json_path = os.path.join(output_dir, "flagged_anomalies.json")
    with open(json_path, "w", encoding="utf-8") as fj:
        json.dump(json_data, fj, indent=2)
    print(f"Successfully generated structured JSON export at: {json_path}")
    
    # Generate CSV (flattened)
    csv_rows = []
    for row in json_data:
        base_info = {
            "row_id": row["row_id"],
            "equipment_id": row["equipment_id"],
            "type": row["type"],
            "site_id": row["site_id"],
            "operator_id": row["operator_id"],
            "check_in": row["check_in"],
            "check_out": row["check_out"],
            "idle_ratio": row["idle_ratio"],
            "is_valid_row": row["is_valid_row"],
            "score": row["score"],
            "severity": row["severity"]
        }
        
        if len(row["flags"]) == 0:
            csv_row = dict(base_info)
            csv_row.update({
                "flag_name": "",
                "flag_category": "",
                "flag_reason": "",
                "flag_details": ""
            })
            csv_rows.append(csv_row)
        else:
            for flag in row["flags"]:
                csv_row = dict(base_info)
                csv_row.update({
                    "flag_name": flag["name"],
                    "flag_category": flag["category"],
                    "flag_reason": flag["reason"],
                    "flag_details": json.dumps(flag["details"])
                })
                csv_rows.append(csv_row)
                
    csv_df = pd.DataFrame(csv_rows)
    csv_path = os.path.join(output_dir, "flagged_anomalies.csv")
    csv_df.to_csv(csv_path, index=False)
    print(f"Successfully generated structured CSV export at: {csv_path}")

def run_pipeline(csv_path, enable_gemini=False, gemini_key=None,
                 now=None, output_dir=None, write_outputs=True):
    """Run the full pipeline over ``csv_path`` and return the scored rows.

    ``now`` overrides the simulated current date used by the overdue and
    booking-conflict rules. It defaults to SIMULATED_CURRENT_DATE so the CLI and
    the fixture test behave exactly as before, but the rest of the project runs
    on a virtual clock at a different date, and two disagreeing "today"s produce
    overdue findings that are wrong in both directions.

    ``output_dir`` overrides where the JSON/CSV exports land; ``write_outputs``
    turns them off entirely, for callers that just want the results in memory.
    """
    # Load dataset
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}")

    current_date = now or SIMULATED_CURRENT_DATE
    if isinstance(current_date, str):
        current_date = datetime.strptime(current_date, "%Y-%m-%d").date()

    # Use keep_default_na=False to keep "NULL" as literal string
    df = pd.read_csv(csv_path, keep_default_na=False)

    # Clean strings
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip()

    # Pre-parse dates and numbers for convenience in downstream modules
    def parse_dt(d):
        if not d or d == "NULL" or d == "nan":
            return None
        return datetime.strptime(d, "%Y-%m-%d").date()

    def parse_fl(v):
        if v == "" or v == "NULL":
            return 0.0
        try:
            return float(v)
        except ValueError:
            return 0.0

    def parse_it(v):
        if v == "" or v == "NULL":
            return None
        try:
            return int(float(v))
        except ValueError:
            return None

    df["parsed_in"] = df["Check_In_Date"].apply(parse_dt)
    df["parsed_out"] = df["Check_Out_Date"].apply(parse_dt)
    df["Engine_Hours_Day"] = df["Engine_Hours_Day"].apply(parse_fl)
    df["Idle_Hours_Day"] = df["Idle_Hours_Day"].apply(parse_fl)
    df["Rental_Days"] = df["Rental_Days"].apply(parse_it)
    df["idle_ratio"] = df.apply(
        lambda r: r["Idle_Hours_Day"] / max(r["Engine_Hours_Day"] + r["Idle_Hours_Day"], 1.0), axis=1
    )

    # 1. Tier 1: validate.py (Integrity Checks)
    invalid_indices, val_flags = validate_records(df, current_date)

    # 2. Filter out failed rows from downstream average calculations
    valid_df = df.drop(index=list(invalid_indices)).copy()

    # 3. Tier 1: asset_rules.py (Basic Asset Rules)
    asset_flags = check_asset_rules(valid_df, current_date, OVERDUE_THRESHOLD_DAYS)

    # 4. Tier 2: self_baseline.py (Equipment-level historical baseline check)
    baseline_flags = check_self_baseline(valid_df)

    # 5. Tier 2: group_analysis.py (Group-level Type/Site/Operator imbalances)
    group_flags = check_group_imbalances(valid_df)

    # 6. Tier 3: severity.py (Combine all flags and score them)
    results = compute_severity_and_consolidate(df, val_flags, asset_flags, baseline_flags, group_flags)

    # 7. Optional Gemini explanation layer (OFF by default)
    if enable_gemini:
        print("Calling optional Gemini explanation layer...")
        from src.explain import explain_anomalies_with_gemini
        results = explain_anomalies_with_gemini(results, api_key=gemini_key)
    else:
        for r in results:
            r["explanation"] = ""

    # Call structured output writer
    if write_outputs:
        if output_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(script_dir, "output")
        write_structured_outputs(results, output_dir)

    return results

def generate_report(results, report_output_path):
    # Formulate the markdown content
    md = []
    md.append("# Anomaly Detection Report - Smart Rental Tracking System\n")
    md.append("This report summarizes the anomaly detection rules, edge case handling, workflow mechanics, and results on the Caterpillar Smart Rental Tracking System telemetry dataset.\n")

    # 1. Table of anomaly types
    md.append("## 1. Implemented Anomaly Types and Core Logic\n")
    md.append("| Check ID | Anomaly Name | Detection Method | Core Formula / Rule Logic | Point Weight |")
    md.append("|---|---|---|---|---|")
    md.append("| 1 | Impossible Hours | Rule-Based | `Engine_Hours_Day + Idle_Hours_Day > 24` | 3 |")
    md.append("| 2 | Bad Date Order | Rule-Based | `Check_Out_Date < Check_In_Date` | 3 |")
    md.append("| 3 | Zero-Activity Row | Rule-Based | `Engine_Hours_Day == 0 AND Idle_Hours_Day == 0` | 3 |")
    md.append("| 4 | Booking Conflict | Rule-Based / Overlap | Same `Equipment_ID` with overlapping `[Check_In_Date, Check_Out_Date]` intervals (active rentals use simulated current date) | 3 |")
    md.append("| 5 | Rental-Days Mismatch | Rule-Based | `abs((Check_Out_Date - Check_In_Date).days - Rental_Days) != 0` | 3 |")
    md.append("| 6 | Unassigned Equipment | Rule-Based | `Site_ID == 'NULL'` | 2 |")
    md.append("| 7 | No Accountability | Rule-Based | `Last_Operator_ID == 'NULL'` | 2 |")
    md.append("| 8 | Under-Utilization | Rule-Based | `Idle_Hours_Day / max(Engine_Hours_Day + Idle_Hours_Day, 1) > 0.75` | 2 |")
    md.append("| 9 | Overdue Rental | Rule-Based / Time-diff | `(SIMULATED_CURRENT_DATE - Check_In_Date).days > 20` for active (no Check_Out_Date) rentals | 2 |")
    md.append("| 10 | Self-Baseline Drift | Statistical Deviation | Current `Engine_Hours_Day` deviates by `> 2` standard deviations from equipment's own prior historical mean | 3 |")
    md.append("| 11 | Type-Level Imbalance | Group Imbalance (Type) | `abs(idle_ratio - Type_Group_Average) > 0.20` | 3 |")
    md.append("| 12 | Site-Level Imbalance | Group Imbalance (Site) | `abs(idle_ratio - Site_Group_Average) > 0.20` (excluding Site_ID == 'NULL') | 3 |")
    md.append("| 13 | Operator-Level Pattern | Group Imbalance (Operator) | `abs(idle_ratio - Operator_Group_Average) > 0.20` (excluding Last_Operator_ID == 'NULL') | 3 |\n")

    # 2. Workflow Mechanics
    md.append("## 2. Workflow Mechanics & Dependencies\n")
    md.append("The anomaly detection module operates as a sequential pipeline with strict execution dependencies:\n")
    md.append(r"""```
[Raw CSV Data] -> [1. validate.py] (Tier 1)
                       |
                       +---> [Invalid Rows] -> Set aside with Integrity Flags (3 pts each)
                       |
                       v
                 [Valid Rows]
                       |
                       +---> [2. asset_rules.py] (Tier 1) ----+ -> Score (2 pts each)
                       |\                                     |
                       +---> [3. self_baseline.py] (Tier 2) --+ -> Score (3 pts each)
                       |\                                     |
                       +---> [4. group_analysis.py] (Tier 2) -+ -> Score (3 pts each)
                                                              |
                                                              v
                                                     [5. severity.py] (Tier 3)
                                                              |
                                                              v
                                                     [Merged Alerts & Scores]
                                                              |
                                                              v
                                                     [(Optional) explain.py]
```
""")
    md.append("- **Step 1 (validate.py):** Runs data integrity checks. This is the **gatekeeper**. Any row that fails validation is flagged and excluded from downstream statistical groupings and baseline calculations. This ensures that erroneous telemetry (like impossible hours or bad date orders) does not pollute the historical averages or group comparison baseline.")
    md.append("- **Step 2 (asset_rules.py):** Performs individual, single-row threshold checks (e.g., missing Site_ID, under-utilization) on valid rows.")
    md.append("- **Step 3 (self_baseline.py):** Compares a row against its equipment's own historical average. This detects individual machine drift over time.")
    md.append("- **Step 4 (group_analysis.py):** Compares the machine's operational pattern (idle ratio) against similar groups (e.g., same equipment Type, same Site, same Operator). This highlights localized or systemic operational outliers.")
    md.append(r"- **Step 5 (severity.py):** Consolidates all flags per row and computes a weighted composite score to categorize rows as Critical (score $\ge 6$), Warning (score $\ge 3$), or Normal (score $< 3$)." + "\n")

    # 3. Edge Cases Table
    md.append("## 3. Edge Cases Handled\n")
    md.append("| Edge Case | Description / Guard | Handled in Module / Function |")
    md.append("|---|---|---|")
    md.append("| Group with < 3 members | Excluded from group comparison to prevent false alarms due to low sample size | `src/group_analysis.py` (`analyze_group_imbalance`) |")
    md.append("| All group members near-identical | A minimum percentage point deviation (20pp) prevents flagging pure background noise | `src/group_analysis.py` (`analyze_group_imbalance`) |")
    md.append("| NULL Site_ID / Operator_ID | Excluded from group averages to avoid skewed baselines, flagged instead under Tier 1 rules | `src/group_analysis.py` (`analyze_group_imbalance`) / `src/asset_rules.py` |")
    md.append("| Integrity-failed rows | Excluded from baseline and group statistics completely to avoid pollution | `main.py` (drops invalid indices before checks) |")
    md.append("| New equipment (0-1 history) | Skips self_baseline entirely to avoid division by zero or false drift alerts | `src/self_baseline.py` (`check_self_baseline`) |")
    md.append("| Same-day return (Rental Days = 0) | Denominators guarded by `max(x, 1)` or safe datetime calculations to prevent division-by-zero | `src/validate.py` / `src/asset_rules.py` |")
    md.append("| Multiple flags on one row | Alerts and points consolidated into a single composite score and row entry | `src/severity.py` (`compute_severity_and_consolidate`) |")
    md.append("| Active rental (no checkout date) | Evaluated using `SIMULATED_CURRENT_DATE = 2025-06-15` to detect overdue status | `src/validate.py` / `src/asset_rules.py` |\n")

    # 4. ML Avoidance & Gemini Isolation
    md.append("## 4. Machine Learning Avoidance and Gemini API Isolation\n")
    md.append("- **Rule-based & Statistical:** No machine learning, fitting, or model training is used in this codebase. All anomaly checks rely strictly on deterministic rules, date differences, percentage differences, or standard deviation math.")
    md.append("- **Gemini API Isolation:** The LLM explanation layer is completely isolated in `src/explain.py`. It is **OFF by default** and is not used to detect anomalies or calculate severity scores. It is strictly an explanation generator that translates existing numerical results into a single plain-language sentence when explicitly enabled via the `--explain` argument and a valid API key.\n")

    # 5. Known Limitations on This Dataset
    md.append("## 5. Known Dataset Limitations due to Sample Size\n")
    md.append("- **Historical Comparison (Self-Baseline):** For equipment with fewer than 2 valid historical rows, the self-baseline check is skipped. In this dataset, several machines (like loaders or new cranes) only have 0-1 prior chronological rows, so they cannot be checked for drift. This is a data-volume limitation, not a logic bug.")
    md.append("- **Group Analysis (Site & Operator Groups):** Several sites and operators in this sample dataset have fewer than 3 valid members. For example, Site `S001` or operators like `OP107` are skipped from group comparisons because their sample sizes are insufficient. Increasing data volume will automatically enable group analysis for these segments.\n")

    # 6. Detailed Flagged Anomalies
    md.append("## 6. Flagged Anomalies in the Telemetry Dataset\n")
    md.append("Below is the list of all flagged anomalies detected in `data/rental_data.csv` using the pipeline rules:\n")
    md.append("| Row Index | Equipment ID | Type | Site ID | Check In | Check Out | Score | Severity Level | Flagged Reasons |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    
    anoms = [r for r in results if r["score"] > 0]
    # Sort by score descending, then row index ascending
    anoms_sorted = sorted(anoms, key=lambda x: (-x["score"], x["row_index"]))
    
    for r in anoms_sorted:
        flags_desc = []
        for f in r["flags"]:
            rule = f["rule"]
            if rule == "impossible_hours":
                flags_desc.append(f"Impossible Hours (Total: {f['total_hours']}h)")
            elif rule == "bad_date_order":
                flags_desc.append("Bad Date Order (Checkout before checkin)")
            elif rule == "zero_activity":
                flags_desc.append("Zero-Activity Row")
            elif rule == "rental_days_mismatch":
                flags_desc.append(f"Rental Days Mismatch (Stated: {f['stated_days']}, Actual: {f['actual_days']})")
            elif rule == "booking_conflict":
                flags_desc.append(f"Booking Conflict (Conflicting Row: {f['conflicting_row_index']})")
            elif rule == "unassigned_equipment":
                flags_desc.append("Unassigned Equipment (Site is NULL)")
            elif rule == "no_accountability":
                flags_desc.append("No Accountability (Operator is NULL)")
            elif rule == "under_utilized":
                flags_desc.append(f"Under-utilized (Idle ratio: {f['idle_ratio']:.2%})")
            elif rule == "overdue":
                flags_desc.append(f"Overdue Active Rental ({f['days_active']} days active)")
            elif rule == "self_baseline_deviation":
                flags_desc.append(f"Self-Baseline Deviation ({f['deviation_stdevs']:.2f} SD)")
            elif rule.endswith("_level_imbalance"):
                g_col = rule.replace("_level_imbalance", "").replace("id", "ID").replace("last_operator_", "Operator ").title()
                flags_desc.append(f"{g_col} Imbalance (Idle ratio: {f['idle_ratio']:.2%}, Group avg: {f['group_average']:.2%})")
        
        flags_str = "; ".join(flags_desc)
        md.append(f"| {r['row_index']} | {r['Equipment_ID']} | {r['Type']} | {r['Site_ID']} | {r['Check_In_Date']} | {r['Check_Out_Date']} | {r['score']} | **{r['level']}** | {flags_str} |")

    # Save to path
    with open(report_output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print(f"Successfully generated final report at: {report_output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="End-to-End Anomaly Detection Pipeline")
    parser.add_argument("--csv", type=str, default="data/rental_data.csv", help="Path to telemetry CSV data file")
    parser.add_argument("--explain", action="store_true", help="Enable optional Gemini plain-language explanations")
    parser.add_argument("--key", type=str, default=None, help="Gemini API Key (optional, defaults to GEMINI_API_KEY environment variable)")
    parser.add_argument("--report", type=str, default="ANOMALY_REPORT.md", help="Output path for the Markdown anomaly report")
    parser.add_argument("--now", type=str, default=None, help="Simulated current date, YYYY-MM-DD (default: %s)" % SIMULATED_CURRENT_DATE)
    args = parser.parse_args()

    # If csv path is relative to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file = args.csv
    if not os.path.isabs(csv_file):
        csv_file = os.path.join(script_dir, csv_file)

    report_path = args.report
    if not os.path.isabs(report_path):
        report_path = os.path.join(script_dir, report_path)

    print("Running smart rental tracking anomaly detection pipeline...")
    print(f"Data source: {csv_file}")
    print(f"Simulated Current Date: {args.now or SIMULATED_CURRENT_DATE}")
    print(f"Overdue Threshold: {OVERDUE_THRESHOLD_DAYS} days")

    try:
        results = run_pipeline(csv_file, enable_gemini=args.explain,
                               gemini_key=args.key, now=args.now)
        
        # Print summary statistics
        total = len(results)
        critical = sum(1 for r in results if r["level"] == "Critical")
        warning = sum(1 for r in results if r["level"] == "Warning")
        normal = sum(1 for r in results if r["level"] == "Normal")

        print("\nPipeline execution complete.")
        print(f"Processed: {total} rows")
        print(f"  - Critical Anomalies: {critical}")
        print(f"  - Warning Anomalies : {warning}")
        print(f"  - Normal Rows       : {normal}")

        # Display Top anomalies
        print("\nTop Flagged Anomalies:")
        anom_results = [r for r in results if r["score"] > 0]
        anom_results_sorted = sorted(anom_results, key=lambda x: x["score"], reverse=True)
        for idx, r in enumerate(anom_results_sorted[:10]):
            print(f"Row {r['row_index']} | {r['Equipment_ID']} ({r['Type']}) | Score: {r['score']} ({r['level']})")
            for f in r["flags"]:
                print(f"  - {f['rule']}: {f}")

        # Generate report
        generate_report(results, report_path)

        # The report used to be copied up to the repo root as well. Dropped:
        # writing outside your own directory surprises every other module, and
        # --report already accepts any path you want it at.

    except Exception as e:
        print(f"Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
