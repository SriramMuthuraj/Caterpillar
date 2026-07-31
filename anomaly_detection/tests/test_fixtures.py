import os
import sys
import unittest
import pandas as pd
from datetime import datetime

# Adjust path to import from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.validate import validate_records
from src.asset_rules import check_asset_rules, SIMULATED_CURRENT_DATE, OVERDUE_THRESHOLD_DAYS
from src.self_baseline import check_self_baseline
from src.group_analysis import check_group_imbalances
from src.severity import compute_severity_and_consolidate

class TestSmartRentalTrackingAnomalyDetection(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Load the rental data CSV dynamically
        cls.data_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "data", "rental_data.csv"
        ))
        cls.df = pd.read_csv(cls.data_path, keep_default_na=False)

        # Clean strings
        for col in cls.df.columns:
            if cls.df[col].dtype == object:
                cls.df[col] = cls.df[col].astype(str).str.strip()

        # Parse helper columns
        def parse_dt(d):
            if not d or d == "NULL" or d == "nan":
                return None
            return datetime.strptime(d, "%Y-%m-%d").date()

        def parse_fl(v):
            if v == "" or v == "NULL":
                return 0.0
            return float(v)

        def parse_it(v):
            if v == "" or v == "NULL":
                return None
            return int(float(v))

        cls.df["parsed_in"] = cls.df["Check_In_Date"].apply(parse_dt)
        cls.df["parsed_out"] = cls.df["Check_Out_Date"].apply(parse_dt)
        cls.df["Engine_Hours_Day"] = cls.df["Engine_Hours_Day"].apply(parse_fl)
        cls.df["Idle_Hours_Day"] = cls.df["Idle_Hours_Day"].apply(parse_fl)
        cls.df["Rental_Days"] = cls.df["Rental_Days"].apply(parse_it)
        cls.df["idle_ratio"] = cls.df.apply(
            lambda r: r["Idle_Hours_Day"] / max(r["Engine_Hours_Day"] + r["Idle_Hours_Day"], 1.0), axis=1
        )

        # Expected Hand-Verified Results mapping: (Equipment_ID, Check_In_Date) -> (score, level, set of rules)
        # All other rows default to (0, "Normal", set())
        cls.hand_verified = {
            # Format: (Equipment_ID, Check_In_Date): (expected_score, expected_level, expected_rules_set)
            ("EQX1001", "2025-02-24"): (3, "Warning", {"self_baseline_deviation"}),
            ("EQX1002", "2025-02-16"): (3, "Warning", {"last_operator_id_level_imbalance"}),
            ("EQX1003", "2025-02-14"): (3, "Warning", {"self_baseline_deviation"}),
            ("EQX1004", "2025-01-05"): (3, "Warning", {"last_operator_id_level_imbalance"}),
            ("EQX1004", "2025-02-04"): (6, "Critical", {"self_baseline_deviation", "site_id_level_imbalance"}),
            ("EQX2002", "2025-01-23"): (3, "Warning", {"site_id_level_imbalance"}),
            ("EQX2003", "2025-02-16"): (3, "Warning", {"self_baseline_deviation"}),
            ("EQX3002", "2025-01-05"): (3, "Warning", {"last_operator_id_level_imbalance"}),
            ("EQX3002", "2025-02-08"): (3, "Warning", {"self_baseline_deviation"}),
            ("EQX3003", "2025-01-28"): (3, "Warning", {"last_operator_id_level_imbalance"}),
            ("EQX4001", "2025-02-08"): (3, "Warning", {"self_baseline_deviation"}),
            ("EQX5001", "2025-02-15"): (3, "Warning", {"self_baseline_deviation"}),
            ("EQX1005", "2025-01-05"): (11, "Critical", {"under_utilized", "type_level_imbalance", "site_id_level_imbalance", "last_operator_id_level_imbalance"}),
            ("EQX1005", "2025-01-30"): (11, "Critical", {"under_utilized", "type_level_imbalance", "site_id_level_imbalance", "last_operator_id_level_imbalance"}),
            ("EQX1005", "2025-02-18"): (11, "Critical", {"under_utilized", "type_level_imbalance", "site_id_level_imbalance", "last_operator_id_level_imbalance"}),
            ("EQX1006", "2025-02-12"): (3, "Warning", {"self_baseline_deviation"}),
            ("EQX2005", "2025-02-15"): (12, "Critical", {"self_baseline_deviation", "type_level_imbalance", "site_id_level_imbalance", "last_operator_id_level_imbalance"}),
            ("EQX6003", "2025-04-14"): (8, "Critical", {"under_utilized", "type_level_imbalance", "site_id_level_imbalance"}),
            ("EQX6004", "2025-04-16"): (11, "Critical", {"under_utilized", "type_level_imbalance", "site_id_level_imbalance", "last_operator_id_level_imbalance"}),
            ("EQX6005", "2025-04-18"): (11, "Critical", {"under_utilized", "type_level_imbalance", "site_id_level_imbalance", "last_operator_id_level_imbalance"}),
            ("EQX6006", "2025-04-20"): (11, "Critical", {"under_utilized", "type_level_imbalance", "site_id_level_imbalance", "last_operator_id_level_imbalance"}),
            ("EQX1002", "2025-04-01"): (5, "Warning", {"unassigned_equipment", "self_baseline_deviation"}),
            ("EQX2003", "2025-04-02"): (5, "Warning", {"no_accountability", "self_baseline_deviation"}),
            ("EQX4003", "2025-04-05"): (14, "Critical", {"under_utilized", "self_baseline_deviation", "type_level_imbalance", "site_id_level_imbalance", "last_operator_id_level_imbalance"}),
            ("EQX3003", "2025-04-06"): (3, "Warning", {"impossible_hours"}),
            ("EQX5002", "2025-05-10"): (6, "Critical", {"bad_date_order", "rental_days_mismatch"}),
            ("EQX2004", "2025-04-08"): (3, "Warning", {"zero_activity"}),
            ("EQX3004", "2025-01-22"): (3, "Warning", {"rental_days_mismatch"}),
            ("EQX4004", "2025-05-01"): (3, "Warning", {"booking_conflict"}),
            ("EQX4004", "2025-05-10"): (3, "Warning", {"booking_conflict"}),
            ("EQX1003", "2025-05-15"): (5, "Warning", {"overdue", "self_baseline_deviation"}),
        }

    def test_pipeline_matches_hand_verified(self):
        # 1. Run validation
        invalid_indices, val_flags = validate_records(self.df, SIMULATED_CURRENT_DATE)

        # 2. Filter valid records for downstream checks
        valid_df = self.df.drop(index=list(invalid_indices)).copy()

        # 3. Run asset rules
        asset_flags = check_asset_rules(valid_df, SIMULATED_CURRENT_DATE, OVERDUE_THRESHOLD_DAYS)

        # 4. Run self baseline
        baseline_flags = check_self_baseline(valid_df)

        # 5. Run group analysis
        group_flags = check_group_imbalances(valid_df)

        # 6. Consolidate into composite severity results
        results = compute_severity_and_consolidate(
            self.df, val_flags, asset_flags, baseline_flags, group_flags
        )

        self.assertEqual(len(results), len(self.df), "Pipeline must return results for all rows.")

        # Verify each row matches the hand-verified expectation
        mismatches = []
        for r in results:
            eq_id = r["Equipment_ID"]
            check_in = r["Check_In_Date"]
            key = (eq_id, check_in)

            # Get hand-verified expectation or default to Normal/0
            if key in self.hand_verified:
                exp_score, exp_level, exp_rules = self.hand_verified[key]
            else:
                exp_score, exp_level, exp_rules = 0, "Normal", set()

            actual_score = r["score"]
            actual_level = r["level"]
            actual_rules = {f["rule"] for f in r["flags"]}

            # Check matching
            if actual_score != exp_score or actual_level != exp_level or actual_rules != exp_rules:
                mismatches.append(
                    f"Row {r['row_index']} ({eq_id} on {check_in}):\n"
                    f"  Expected: Score={exp_score}, Level={exp_level}, Rules={exp_rules}\n"
                    f"  Actual  : Score={actual_score}, Level={actual_level}, Rules={actual_rules}"
                )

        if mismatches:
            mismatches_str = "\n\n".join(mismatches)
            self.fail(f"Pipeline output mismatches found on {len(mismatches)} rows:\n\n{mismatches_str}")

if __name__ == "__main__":
    unittest.main()
