import os
import sys
import json
import pandas as pd
import numpy as np
import altair as alt
import streamlit as st
from datetime import datetime

# Configure page
st.set_page_config(page_title="Anomaly Detection Dashboard", page_icon="🚜", layout="wide")

# Inject premium styling
st.markdown("""
<style>
    /* Styling for metrics cards */
    [data-testid="stMetricValue"] {
        font-family: 'Outfit', 'Inter', sans-serif;
        font-size: 28px;
        font-weight: 700;
        color: #1E3A8A; /* Premium Deep Blue */
    }
    [data-testid="stMetricLabel"] {
        font-family: 'Inter', sans-serif;
        font-size: 14px;
        font-weight: 500;
        color: #4B5563; /* Sleek Grey */
    }
    /* Main titles */
    h1 {
        font-family: 'Outfit', 'Inter', sans-serif;
        background: linear-gradient(90deg, #1E3A8A 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    h2, h3 {
        font-family: 'Outfit', 'Inter', sans-serif;
        color: #1F2937;
        font-weight: 600;
    }
    /* Styled buttons */
    .stButton>button {
        border-radius: 8px;
        background-color: #3B82F6;
        color: white;
        border: none;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #2563EB;
        transform: translateY(-2px);
    }
</style>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700;800&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

# Add local directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

from main import run_pipeline
from src.explain import explain_anomalies_with_gemini

# Set default data path
csv_path = os.path.join(script_dir, "data", "rental_data.csv")

# 1. Pipeline Execution & Caching
@st.cache_data
def get_pipeline_data(csv_file):
    # This runs the pipeline and outputs the structured JSON and CSV reports
    results = run_pipeline(csv_file)
    
    # Read the JSON anomalies
    output_dir = os.path.join(script_dir, "output")
    json_path = os.path.join(output_dir, "flagged_anomalies.json")
    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
        
    return results, json_data

# Run pipeline
with st.spinner("Processing telemetry pipeline..."):
    results, json_data = get_pipeline_data(csv_path)

# Map row_id to other raw metadata
row_info_map = {
    r["row_index"]: {
        "engine_hours": r["Engine_Hours_Day"],
        "idle_hours": r["Idle_Hours_Day"],
        "rental_days": r["Rental_Days"],
        "operator_id": r["Last_Operator_ID"]
    }
    for r in results
}

# Page Header
st.title("Smart Rental Anomaly Detection Verification Dashboard")
st.write("Diagnostic harness & visual interface to verify rules, edge cases, and baseline deviations in the telemetry pipeline.")

# Define main tabs
tab1, tab2, tab3 = st.tabs([
    "📊 Main Workspace", 
    "📈 Group Analysis & Verification", 
    "⚠️ Edge Case Verification"
])

# Sidebar Controls
st.sidebar.header("🎯 Filter Controls")

# Sidebar Severity Filter
severity_options = ["Critical", "Warning", "Normal"]
severity_filter = st.sidebar.multiselect(
    "Severity Level", 
    options=severity_options, 
    default=severity_options
)

# Sidebar Type Filter
unique_types = sorted(list(set(r["type"] for r in json_data)))
type_filter = st.sidebar.multiselect("Equipment Type", options=unique_types)

# Sidebar Site ID Filter
unique_sites = sorted(list(set(r["site_id"] for r in json_data)))
site_filter = st.sidebar.multiselect("Site ID", options=unique_sites)

# Sidebar Operator ID Filter
unique_operators = sorted(list(set(r["operator_id"] for r in json_data)))
op_filter = st.sidebar.multiselect("Operator ID", options=unique_operators)

# Sidebar Search
eq_id_search = st.sidebar.text_input("Search Equipment ID", "")

# Sidebar Flags Checkbox
only_flagged = st.sidebar.checkbox("Show only rows with at least one flag", value=False)

# Sidebar Gemini Settings
st.sidebar.markdown("---")
st.sidebar.header("🤖 AI Explanation Layer")
enable_gemini = st.sidebar.toggle("Enable Gemini explanations", value=False)
gemini_key = st.sidebar.text_input("GEMINI_API_KEY", type="password", help="Session-only API key, never saved to disk")

# Apply Sidebar Filters
filtered_data = []
for r in json_data:
    if severity_filter and r["severity"] not in severity_filter:
        continue
    if type_filter and r["type"] not in type_filter:
        continue
    if site_filter and r["site_id"] not in site_filter:
        continue
    if op_filter and r["operator_id"] not in op_filter:
        continue
    if eq_id_search and eq_id_search.strip().lower() not in r["equipment_id"].lower():
        continue
    if only_flagged and r["score"] == 0:
        continue
    filtered_data.append(r)

# Tab 1: Main Workspace
with tab1:
    # 1. Metrics Row
    total_rows = len(json_data)
    valid_rows = sum(1 for r in json_data if r["is_valid_row"])
    invalid_rows = total_rows - valid_rows
    
    crit_cnt = sum(1 for r in json_data if r["severity"] == "Critical")
    warn_cnt = sum(1 for r in json_data if r["severity"] == "Warning")
    norm_cnt = sum(1 for r in json_data if r["severity"] == "Normal")
    
    valid_idle_ratios = [r["idle_ratio"] for r in json_data if r["is_valid_row"] and r["idle_ratio"] is not None]
    avg_idle_ratio = np.mean(valid_idle_ratios) if valid_idle_ratios else 0.0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Rows Loaded", f"{total_rows}")
    col2.metric("Validation Status", f"{valid_rows} valid / {invalid_rows} invalid", delta=f"-{invalid_rows} excluded", delta_color="inverse")
    col3.metric("Severity (C / W / N)", f"{crit_cnt} / {warn_cnt} / {norm_cnt}")
    col4.metric("Avg Idle Ratio (Valid)", f"{avg_idle_ratio:.1%}")
    
    st.markdown("---")
    
    # 2. Main Data Table
    st.subheader("📋 Equipment Rentals Data Table")
    if filtered_data:
        table_rows = []
        for r in filtered_data:
            table_rows.append({
                "Equipment_ID": r["equipment_id"],
                "Type": r["type"],
                "Site_ID": r["site_id"],
                "Operator_ID": r["operator_id"],
                "Check_In": r["check_in"],
                "Check_Out": r["check_out"],
                "Idle_Ratio": r["idle_ratio"],
                "Score": r["score"],
                "Severity": r["severity"]
            })
            
        df_display = pd.DataFrame(table_rows)
        # Default sort by Score descending
        df_display = df_display.sort_values(by="Score", ascending=False)
        
        # Color coding for severity column
        def style_severity(val):
            if val == "Critical":
                return "background-color: #fee2e2; color: #991b1b; font-weight: bold;"
            elif val == "Warning":
                return "background-color: #ffedd5; color: #9a3412; font-weight: bold;"
            elif val == "Normal":
                return "background-color: #dcfce7; color: #166534;"
            return ""
            
        if hasattr(df_display.style, "map"):
            styled_df = df_display.style.format({"Idle_Ratio": lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"}).map(style_severity, subset=["Severity"])
        else:
            styled_df = df_display.style.format({"Idle_Ratio": lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"}).applymap(style_severity, subset=["Severity"])
            
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.info("No records matched the selected filters.")
        
    st.markdown("---")
    
    # 3. Row Detail Drill-down
    st.subheader("🔍 Record Details & Historical Drill-Down")
    if filtered_data:
        options = [f"{r['equipment_id']} (Checked in: {r['check_in']})" for r in filtered_data]
        selected_option = st.selectbox("Select equipment rental record to inspect:", options)
        
        selected_idx = options.index(selected_option)
        selected_row = filtered_data[selected_idx]
        selected_row_info = row_info_map[selected_row["row_id"]]
        
        # Grid details
        det_col1, det_col2, det_col3 = st.columns(3)
        det_col1.write(f"**Equipment ID:** {selected_row['equipment_id']}")
        det_col1.write(f"**Equipment Type:** {selected_row['type']}")
        det_col1.write(f"**Site ID:** {selected_row['site_id']}")
        
        det_col2.write(f"**Operator ID:** {selected_row['operator_id']}")
        det_col2.write(f"**Check In:** {selected_row['check_in']}")
        det_col2.write(f"**Check Out:** {selected_row['check_out'] if selected_row['check_out'] else 'Active Rental'}")
        
        idle_pct_str = f"{selected_row['idle_ratio']:.2%}" if selected_row['idle_ratio'] is not None else "N/A"
        det_col3.write(f"**Idle Ratio:** {idle_pct_str}")
        det_col3.write(f"**Composite Score:** {selected_row['score']}")
        det_col3.write(f"**Severity Level:** {selected_row['severity']}")
        
        # Display fired flags
        st.markdown("#### Fired Flags & Reasons")
        if selected_row["flags"]:
            for flag in selected_row["flags"]:
                with st.expander(f"🚩 Rule Fired: **{flag['name']}** ({flag['category']})"):
                    st.write(f"**Reason:** {flag['reason']}")
                    st.write("**Raw Numeric Details:**")
                    st.json(flag["details"])
        else:
            st.success("No anomaly flags fired on this rental record.")
            
        # Line chart for self baseline
        has_self_baseline_flag = any(f["name"] == "self_baseline_deviation" for f in selected_row["flags"])
        if has_self_baseline_flag:
            st.markdown("#### Chronological Engine Hours & Self-Baseline Drift")
            # Get valid chronological history for this machine
            eq_history = [
                r for r in json_data 
                if r["equipment_id"] == selected_row["equipment_id"] and r["is_valid_row"]
            ]
            eq_history = sorted(eq_history, key=lambda x: x["check_in"])
            
            hist_data = []
            for r in eq_history:
                row_id = r["row_id"]
                info = row_info_map[row_id]
                hist_data.append({
                    "Date": r["check_in"],
                    "Engine Hours": info["engine_hours"],
                    "Is Current": (row_id == selected_row["row_id"])
                })
            hist_df = pd.DataFrame(hist_data)
            
            line_chart = alt.Chart(hist_df).mark_line(point=True).encode(
                x=alt.X('Date:T', title='Check-in Date'),
                y=alt.Y('Engine Hours:Q', title='Engine Hours / Day'),
                tooltip=['Date', 'Engine Hours']
            )
            
            points_chart = alt.Chart(hist_df).mark_circle(size=100).encode(
                x='Date:T',
                y='Engine Hours:Q',
                color=alt.condition(
                    alt.datum['Is Current'] == True,
                    alt.value('#ef4444'), # Highlighting current in Red
                    alt.value('#3b82f6')
                ),
                tooltip=['Date', 'Engine Hours']
            )
            
            combined_chart = (line_chart + points_chart).properties(
                title=f"Historical Engine Hours per Day for {selected_row['equipment_id']}",
                height=300
            )
            st.altair_chart(combined_chart, use_container_width=True)
            
        # Bar chart for group imbalance
        group_flags = [f for f in selected_row["flags"] if f["category"] == "group"]
        if group_flags:
            st.markdown("#### Group Imbalance Comparisons")
            # Display charts side by side if multiple group flags triggered
            g_cols = st.columns(len(group_flags))
            for i, gf in enumerate(group_flags):
                with g_cols[i]:
                    g_name = gf["name"]
                    g_val = gf["details"].get("group_value")
                    row_idle = gf["details"].get("idle_ratio")
                    group_avg = gf["details"].get("group_average")
                    
                    g_label = g_name.replace("_level_imbalance", "").replace("id", "ID").replace("last_operator_", "Operator ").title()
                    
                    comp_df = pd.DataFrame([
                        {"Category": "This Rental", "Idle Ratio": row_idle},
                        {"Category": f"Group Avg ({g_val})", "Idle Ratio": group_avg}
                    ])
                    
                    bar_chart = alt.Chart(comp_df).mark_bar(size=40).encode(
                        x=alt.X('Category:N', title='', sort=None),
                        y=alt.Y('Idle Ratio:Q', title='Idle Ratio', axis=alt.Axis(format='%')),
                        color=alt.Color('Category:N', scale=alt.Scale(domain=['This Rental', f"Group Avg ({g_val})"], range=['#ef4444', '#3b82f6']), legend=None),
                        tooltip=['Category', 'Idle Ratio']
                    ).properties(
                        title=f"{g_label} Comparison ({g_val})",
                        height=250
                    )
                    st.altair_chart(bar_chart, use_container_width=True)
                    
        # On-Demand Gemini Explanations
        if selected_row["severity"] == "Critical":
            st.markdown("#### AI Anomaly Explanation")
            if enable_gemini:
                if not gemini_key:
                    st.warning("🔑 Please enter a session-only GEMINI_API_KEY in the sidebar to run Gemini explanations.")
                else:
                    if st.button("Generate Explanation with Gemini", key=f"gem_explain_{selected_row['row_id']}"):
                        with st.spinner("Invoking Gemini models in fallback chain..."):
                            original_row = None
                            for r in results:
                                if r["row_index"] == selected_row["row_id"]:
                                    original_row = r
                                    break
                            
                            if original_row:
                                # Send single row context as a copy list to explain
                                row_copy = [dict(original_row)]
                                explained = explain_anomalies_with_gemini(row_copy, api_key=gemini_key)
                                explanation = explained[0].get("explanation", "")
                                if explanation:
                                    st.success(f"**Gemini explanation:** {explanation}")
                                else:
                                    st.error("Fallback chain returned empty. API quota exceeded or connection failure.")
                            else:
                                st.error("Selected record could not be mapped back to original telemetry format.")
            else:
                st.info("💡 Turn on 'Enable Gemini explanations' in the sidebar to ask Gemini to explain this critical anomaly.")
    else:
        st.info("No rows to inspect.")
        
    st.markdown("---")
    
    # 4. Exports Section
    st.subheader("📥 Export Outputs")
    if filtered_data:
        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            csv_data = df_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Filtered Table (CSV)",
                data=csv_data,
                file_name="filtered_anomalies.csv",
                mime="text/csv"
            )
        with exp_col2:
            unfiltered_json_str = json.dumps(json_data, indent=2)
            st.download_button(
                label="Download Full structured Anomalies (JSON)",
                data=unfiltered_json_str,
                file_name="flagged_anomalies.json",
                mime="application/json"
            )

# Tab 2: Group Analysis & Verification
with tab2:
    st.header("Group-Level Idle Ratio Comparison Engine")
    st.write("This section visualizes the averages across all groups. Groups with **fewer than 3 valid members** (marked in grey) are skipped by the pipeline comparisons.")
    
    for col, label in [("type", "Equipment Type"), ("site_id", "Site ID"), ("operator_id", "Operator ID")]:
        filtered = [r for r in json_data if r["is_valid_row"] and r[col] != "NULL" and r[col] != ""]
        
        if not filtered:
            st.warning(f"No valid records for {label} groups.")
            continue
            
        group_records = {}
        for r in filtered:
            val = r[col]
            if val not in group_records:
                group_records[val] = []
            if r["idle_ratio"] is not None:
                group_records[val].append(r["idle_ratio"])
                
        group_stats = []
        for val, ratios in group_records.items():
            count = len(ratios)
            avg_idle = np.mean(ratios) if ratios else 0.0
            status = "Active (n≥3)" if count >= 3 else "Skipped (n<3)"
            group_stats.append({
                "Group Label": f"{val} (n={count})",
                "Group Value": val,
                "Average Idle Ratio": avg_idle,
                "n": count,
                "Status": status
            })
            
        group_stats_df = pd.DataFrame(group_stats)
        
        if not group_stats_df.empty:
            chart = alt.Chart(group_stats_df).mark_bar().encode(
                x=alt.X('Group Label:N', title=label, sort='-y'),
                y=alt.Y('Average Idle Ratio:Q', title='Average Idle Ratio', axis=alt.Axis(format='%')),
                color=alt.Color('Status:N', scale=alt.Scale(domain=['Active (n≥3)', 'Skipped (n<3)'], range=['#3b82f6', '#9ca3af'])),
                tooltip=['Group Value', 'Average Idle Ratio', 'n', 'Status']
            ).properties(
                title=f"Average Idle Ratio by {label}",
                height=300
            )
            st.altair_chart(chart, use_container_width=True)

# Tab 3: Edge Case Verification
with tab3:
    st.header("⚙️ Telemetry Edge Cases & Pipeline Guards")
    st.write("Confirming the pipeline's handling of documented edge cases via live records pulled from the dataset.")
    
    # 1. Excluded from group baselines (Tier 1 validation failures)
    invalid_rows = [r for r in json_data if not r["is_valid_row"]]
    st.subheader("1. Rows Excluded from Baselines (Tier 1 Failures)")
    st.write(f"**Fired:** {len(invalid_rows)} record(s) excluded.")
    if invalid_rows:
        inv_df = pd.DataFrame([
            {
                "Row ID": r["row_id"],
                "Equipment ID": r["equipment_id"],
                "Type": r["type"],
                "Check In": r["check_in"],
                "Check Out": r["check_out"],
                "Failed Integrity Rules": ", ".join(f["name"] for f in r["flags"] if f["category"] == "integrity")
            }
            for r in invalid_rows
        ])
        st.dataframe(inv_df, use_container_width=True, hide_index=True)
    else:
        st.success("No validation failures detected. All rows included in baselines.")
        
    st.markdown("---")
    
    # 2. Equipment with < 2 prior valid rows (self-baseline skipped)
    skipped_self_baseline = []
    valid_rows_sorted = sorted([r for r in json_data if r["is_valid_row"]], key=lambda x: x["check_in"])
    
    for r in valid_rows_sorted:
        eq_id = r["equipment_id"]
        curr_in = datetime.strptime(r["check_in"], "%Y-%m-%d").date() if r["check_in"] else None
        if not curr_in:
            continue
        
        prior_count = 0
        for pr in valid_rows_sorted:
            if pr["equipment_id"] == eq_id:
                pr_in = datetime.strptime(pr["check_in"], "%Y-%m-%d").date() if pr["check_in"] else None
                if pr_in and pr_in < curr_in:
                    prior_count += 1
                    
        if prior_count < 2:
            skipped_self_baseline.append({
                "Row ID": r["row_id"],
                "Equipment ID": eq_id,
                "Type": r["type"],
                "Check In": r["check_in"],
                "Prior Valid Chronological Rows": prior_count
            })
            
    st.subheader("2. Self-Baseline Skipped (New Equipment, <2 Prior Valid Rows)")
    st.write(f"**Fired:** {len(skipped_self_baseline)} record(s) skipped drift calculations.")
    if skipped_self_baseline:
        sb_df = pd.DataFrame(skipped_self_baseline)
        st.dataframe(sb_df, use_container_width=True, hide_index=True)
    else:
        st.success("All valid equipment rentals have sufficient history for baseline.")
        
    st.markdown("---")
    
    # 3. Groups with < 3 members (group analysis skipped)
    skipped_groups = []
    for col, label in [("type", "Equipment Type"), ("site_id", "Site ID"), ("operator_id", "Operator ID")]:
        vals = [r[col] for r in json_data if r["is_valid_row"] and r[col] != "NULL" and r[col] != ""]
        unique_vals = set(vals)
        for uv in unique_vals:
            count = vals.count(uv)
            if count < 3:
                skipped_groups.append({
                    "Group Dimension": label,
                    "Group Value": uv,
                    "Valid Members Count": count
                })
                
    st.subheader("3. Group Averages Skipped (Low Sample Size, <3 Members)")
    st.write(f"**Fired:** {len(skipped_groups)} group(s) skipped to prevent false comparison alarms.")
    if skipped_groups:
        sg_df = pd.DataFrame(skipped_groups)
        st.dataframe(sg_df, use_container_width=True, hide_index=True)
    else:
        st.success("All groups have 3 or more members.")
        
    st.markdown("---")
    
    # 4. Self-baseline zero-variance sentinel case
    zero_variance_rows = []
    for r in json_data:
        for f in r["flags"]:
            if f["name"] == "self_baseline_deviation" and f["details"].get("historical_std") == 0.0:
                zero_variance_rows.append({
                    "Row ID": r["row_id"],
                    "Equipment ID": r["equipment_id"],
                    "Check In": r["check_in"],
                    "Engine Hours": f["details"].get("engine_hours"),
                    "Historical Mean": f["details"].get("historical_mean"),
                    "Historical Std Dev": "insufficient variance in history",
                    "Computed Deviation (SD)": f["details"].get("deviation_stdevs")
                })
                
    st.subheader("4. Self-Baseline Zero-Variance Sentinel Case")
    st.write(f"**Fired:** {len(zero_variance_rows)} record(s) triggered standard deviation sentinel.")
    if zero_variance_rows:
        zv_df = pd.DataFrame(zero_variance_rows)
        st.dataframe(zv_df, use_container_width=True, hide_index=True)
    else:
        st.info("No zero-variance cases triggered in this dataset.")
