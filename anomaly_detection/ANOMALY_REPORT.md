# Anomaly Detection Report - Smart Rental Tracking System

This report summarizes the anomaly detection rules, edge case handling, workflow mechanics, and results on the Caterpillar Smart Rental Tracking System telemetry dataset.

## 1. Implemented Anomaly Types and Core Logic

| Check ID | Anomaly Name | Detection Method | Core Formula / Rule Logic | Point Weight |
|---|---|---|---|---|
| 1 | Impossible Hours | Rule-Based | `Engine_Hours_Day + Idle_Hours_Day > 24` | 3 |
| 2 | Bad Date Order | Rule-Based | `Check_Out_Date < Check_In_Date` | 3 |
| 3 | Zero-Activity Row | Rule-Based | `Engine_Hours_Day == 0 AND Idle_Hours_Day == 0` | 3 |
| 4 | Booking Conflict | Rule-Based / Overlap | Same `Equipment_ID` with overlapping `[Check_In_Date, Check_Out_Date]` intervals (active rentals use simulated current date) | 3 |
| 5 | Rental-Days Mismatch | Rule-Based | `abs((Check_Out_Date - Check_In_Date).days - Rental_Days) != 0` | 3 |
| 6 | Unassigned Equipment | Rule-Based | `Site_ID == 'NULL'` | 2 |
| 7 | No Accountability | Rule-Based | `Last_Operator_ID == 'NULL'` | 2 |
| 8 | Under-Utilization | Rule-Based | `Idle_Hours_Day / max(Engine_Hours_Day + Idle_Hours_Day, 1) > 0.75` | 2 |
| 9 | Overdue Rental | Rule-Based / Time-diff | `(SIMULATED_CURRENT_DATE - Check_In_Date).days > 20` for active (no Check_Out_Date) rentals | 2 |
| 10 | Self-Baseline Drift | Statistical Deviation | Current `Engine_Hours_Day` deviates by `> 2` standard deviations from equipment's own prior historical mean | 3 |
| 11 | Type-Level Imbalance | Group Imbalance (Type) | `abs(idle_ratio - Type_Group_Average) > 0.20` | 3 |
| 12 | Site-Level Imbalance | Group Imbalance (Site) | `abs(idle_ratio - Site_Group_Average) > 0.20` (excluding Site_ID == 'NULL') | 3 |
| 13 | Operator-Level Pattern | Group Imbalance (Operator) | `abs(idle_ratio - Operator_Group_Average) > 0.20` (excluding Last_Operator_ID == 'NULL') | 3 |

## 2. Workflow Mechanics & Dependencies

The anomaly detection module operates as a sequential pipeline with strict execution dependencies:

```
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

- **Step 1 (validate.py):** Runs data integrity checks. This is the **gatekeeper**. Any row that fails validation is flagged and excluded from downstream statistical groupings and baseline calculations. This ensures that erroneous telemetry (like impossible hours or bad date orders) does not pollute the historical averages or group comparison baseline.
- **Step 2 (asset_rules.py):** Performs individual, single-row threshold checks (e.g., missing Site_ID, under-utilization) on valid rows.
- **Step 3 (self_baseline.py):** Compares a row against its equipment's own historical average. This detects individual machine drift over time.
- **Step 4 (group_analysis.py):** Compares the machine's operational pattern (idle ratio) against similar groups (e.g., same equipment Type, same Site, same Operator). This highlights localized or systemic operational outliers.
- **Step 5 (severity.py):** Consolidates all flags per row and computes a weighted composite score to categorize rows as Critical (score $\ge 6$), Warning (score $\ge 3$), or Normal (score $< 3$).

## 3. Edge Cases Handled

| Edge Case | Description / Guard | Handled in Module / Function |
|---|---|---|
| Group with < 3 members | Excluded from group comparison to prevent false alarms due to low sample size | `src/group_analysis.py` (`analyze_group_imbalance`) |
| All group members near-identical | A minimum percentage point deviation (20pp) prevents flagging pure background noise | `src/group_analysis.py` (`analyze_group_imbalance`) |
| NULL Site_ID / Operator_ID | Excluded from group averages to avoid skewed baselines, flagged instead under Tier 1 rules | `src/group_analysis.py` (`analyze_group_imbalance`) / `src/asset_rules.py` |
| Integrity-failed rows | Excluded from baseline and group statistics completely to avoid pollution | `main.py` (drops invalid indices before checks) |
| New equipment (0-1 history) | Skips self_baseline entirely to avoid division by zero or false drift alerts | `src/self_baseline.py` (`check_self_baseline`) |
| Same-day return (Rental Days = 0) | Denominators guarded by `max(x, 1)` or safe datetime calculations to prevent division-by-zero | `src/validate.py` / `src/asset_rules.py` |
| Multiple flags on one row | Alerts and points consolidated into a single composite score and row entry | `src/severity.py` (`compute_severity_and_consolidate`) |
| Active rental (no checkout date) | Evaluated using `SIMULATED_CURRENT_DATE = 2025-06-15` to detect overdue status | `src/validate.py` / `src/asset_rules.py` |

## 4. Machine Learning Avoidance and Gemini API Isolation

- **Rule-based & Statistical:** No machine learning, fitting, or model training is used in this codebase. All anomaly checks rely strictly on deterministic rules, date differences, percentage differences, or standard deviation math.
- **Gemini API Isolation:** The LLM explanation layer is completely isolated in `src/explain.py`. It is **OFF by default** and is not used to detect anomalies or calculate severity scores. It is strictly an explanation generator that translates existing numerical results into a single plain-language sentence when explicitly enabled via the `--explain` argument and a valid API key.

## 5. Known Dataset Limitations due to Sample Size

- **Historical Comparison (Self-Baseline):** For equipment with fewer than 2 valid historical rows, the self-baseline check is skipped. In this dataset, several machines (like loaders or new cranes) only have 0-1 prior chronological rows, so they cannot be checked for drift. This is a data-volume limitation, not a logic bug.
- **Group Analysis (Site & Operator Groups):** Several sites and operators in this sample dataset have fewer than 3 valid members. For example, Site `S001` or operators like `OP107` are skipped from group comparisons because their sample sizes are insufficient. Increasing data volume will automatically enable group analysis for these segments.

## 6. Flagged Anomalies in the Telemetry Dataset

Below is the list of all flagged anomalies detected in `data/rental_data.csv` using the pipeline rules:

| Row Index | Equipment ID | Type | Site ID | Check In | Check Out | Score | Severity Level | Flagged Reasons |
|---|---|---|---|---|---|---|---|---|
| 67 | EQX4003 | Grader | S006 | 2025-04-05 | 2025-04-20 | 14 | **Critical** | Under-utilized (Idle ratio: 83.64%); Self-Baseline Deviation (21.30 SD); Type Imbalance (Idle ratio: 83.64%, Group avg: 37.15%); Site_Id Imbalance (Idle ratio: 83.64%, Group avg: 52.90%); Operator Id Imbalance (Idle ratio: 83.64%, Group avg: 35.96%) |
| 58 | EQX2005 | Bulldozer | S001 | 2025-02-15 | 2025-03-02 | 12 | **Critical** | Self-Baseline Deviation (37.48 SD); Type Imbalance (Idle ratio: 1.67%, Group avg: 30.60%); Site_Id Imbalance (Idle ratio: 1.67%, Group avg: 26.72%); Operator Id Imbalance (Idle ratio: 1.67%, Group avg: 35.96%) |
| 50 | EQX1005 | Excavator | S005 | 2025-01-05 | 2025-01-23 | 11 | **Critical** | Under-utilized (Idle ratio: 89.13%); Type Imbalance (Idle ratio: 89.13%, Group avg: 32.71%); Site_Id Imbalance (Idle ratio: 89.13%, Group avg: 41.67%); Operator Id Imbalance (Idle ratio: 89.13%, Group avg: 32.30%) |
| 51 | EQX1005 | Excavator | S005 | 2025-01-30 | 2025-02-11 | 11 | **Critical** | Under-utilized (Idle ratio: 86.41%); Type Imbalance (Idle ratio: 86.41%, Group avg: 32.71%); Site_Id Imbalance (Idle ratio: 86.41%, Group avg: 41.67%); Operator Id Imbalance (Idle ratio: 86.41%, Group avg: 35.96%) |
| 52 | EQX1005 | Excavator | S006 | 2025-02-18 | 2025-03-08 | 11 | **Critical** | Under-utilized (Idle ratio: 90.00%); Type Imbalance (Idle ratio: 90.00%, Group avg: 32.71%); Site_Id Imbalance (Idle ratio: 90.00%, Group avg: 52.90%); Operator Id Imbalance (Idle ratio: 90.00%, Group avg: 45.40%) |
| 62 | EQX6004 | Bulldozer | S002 | 2025-04-16 | 2025-04-26 | 11 | **Critical** | Under-utilized (Idle ratio: 85.00%); Type Imbalance (Idle ratio: 85.00%, Group avg: 30.60%); Site_Id Imbalance (Idle ratio: 85.00%, Group avg: 31.91%); Operator Id Imbalance (Idle ratio: 85.00%, Group avg: 56.32%) |
| 63 | EQX6005 | Crane | S004 | 2025-04-18 | 2025-04-28 | 11 | **Critical** | Under-utilized (Idle ratio: 82.00%); Type Imbalance (Idle ratio: 82.00%, Group avg: 38.73%); Site_Id Imbalance (Idle ratio: 82.00%, Group avg: 32.70%); Operator Id Imbalance (Idle ratio: 82.00%, Group avg: 56.32%) |
| 64 | EQX6006 | Grader | S005 | 2025-04-20 | 2025-05-01 | 11 | **Critical** | Under-utilized (Idle ratio: 86.00%); Type Imbalance (Idle ratio: 86.00%, Group avg: 37.15%); Site_Id Imbalance (Idle ratio: 86.00%, Group avg: 41.67%); Operator Id Imbalance (Idle ratio: 86.00%, Group avg: 56.32%) |
| 61 | EQX6003 | Loader | S003 | 2025-04-14 | 2025-04-28 | 8 | **Critical** | Under-utilized (Idle ratio: 88.00%); Type Imbalance (Idle ratio: 88.00%, Group avg: 34.12%); Site_Id Imbalance (Idle ratio: 88.00%, Group avg: 33.18%) |
| 13 | EQX1004 | Excavator | S006 | 2025-02-04 | 2025-02-18 | 6 | **Critical** | Self-Baseline Deviation (3.54 SD); Site_Id Imbalance (Idle ratio: 24.44%, Group avg: 52.90%) |
| 69 | EQX5002 | Loader | S004 | 2025-05-10 | 2025-05-02 | 6 | **Critical** | Bad Date Order (Checkout before checkin); Rental Days Mismatch (Stated: 8, Actual: -8) |
| 65 | EQX1002 | Excavator | NULL | 2025-04-01 | 2025-04-16 | 5 | **Warning** | Unassigned Equipment (Site is NULL); Self-Baseline Deviation (6.01 SD) |
| 66 | EQX2003 | Bulldozer | S002 | 2025-04-02 | 2025-04-14 | 5 | **Warning** | No Accountability (Operator is NULL); Self-Baseline Deviation (4.00 SD) |
| 74 | EQX1003 | Excavator | S001 | 2025-05-15 |  | 5 | **Warning** | Overdue Active Rental (31 days active); Self-Baseline Deviation (7.94 SD) |
| 4 | EQX1001 | Excavator | S002 | 2025-02-24 | 2025-03-11 | 3 | **Warning** | Self-Baseline Deviation (100000.00 SD) |
| 7 | EQX1002 | Excavator | S007 | 2025-02-16 | 2025-03-03 | 3 | **Warning** | Operator Id Imbalance (Idle ratio: 20.00%, Group avg: 45.40%) |
| 10 | EQX1003 | Excavator | S007 | 2025-02-14 | 2025-02-28 | 3 | **Warning** | Self-Baseline Deviation (6.36 SD) |
| 11 | EQX1004 | Excavator | S002 | 2025-01-05 | 2025-01-17 | 3 | **Warning** | Operator Id Imbalance (Idle ratio: 17.24%, Group avg: 56.32%) |
| 18 | EQX2002 | Bulldozer | S006 | 2025-01-23 | 2025-02-12 | 3 | **Warning** | Site_Id Imbalance (Idle ratio: 30.85%, Group avg: 52.90%) |
| 22 | EQX2003 | Bulldozer | S005 | 2025-02-16 | 2025-03-08 | 3 | **Warning** | Self-Baseline Deviation (4.95 SD) |
| 29 | EQX3002 | Crane | S003 | 2025-01-05 | 2025-01-19 | 3 | **Warning** | Operator Id Imbalance (Idle ratio: 32.10%, Group avg: 56.32%) |
| 31 | EQX3002 | Crane | S005 | 2025-02-08 | 2025-02-23 | 3 | **Warning** | Self-Baseline Deviation (2.59 SD) |
| 33 | EQX3003 | Crane | S006 | 2025-01-28 | 2025-02-15 | 3 | **Warning** | Operator Id Imbalance (Idle ratio: 35.56%, Group avg: 56.32%) |
| 37 | EQX4001 | Grader | S002 | 2025-02-08 | 2025-02-18 | 3 | **Warning** | Self-Baseline Deviation (4.01 SD) |
| 46 | EQX5001 | Loader | S007 | 2025-02-15 | 2025-03-02 | 3 | **Warning** | Self-Baseline Deviation (2.12 SD) |
| 55 | EQX1006 | Excavator | S001 | 2025-02-12 | 2025-02-27 | 3 | **Warning** | Self-Baseline Deviation (100000.00 SD) |
| 68 | EQX3003 | Crane | S001 | 2025-04-06 | 2025-04-16 | 3 | **Warning** | Impossible Hours (Total: 27.0h) |
| 70 | EQX2004 | Bulldozer | S003 | 2025-04-08 | 2025-04-18 | 3 | **Warning** | Zero-Activity Row |
| 71 | EQX3004 | Crane | S005 | 2025-01-22 | 2025-02-15 | 3 | **Warning** | Rental Days Mismatch (Stated: 25, Actual: 24) |
| 72 | EQX4004 | Grader | S002 | 2025-05-01 | 2025-05-20 | 3 | **Warning** | Booking Conflict (Conflicting Row: 73) |
| 73 | EQX4004 | Grader | S006 | 2025-05-10 | 2025-05-25 | 3 | **Warning** | Booking Conflict (Conflicting Row: 72) |
