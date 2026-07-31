import pandas as pd

def analyze_group_imbalance(valid_df, groupby_col, target_col="idle_ratio", min_members=3, threshold=0.20):
    """
    Generic group analysis function.
    Groups valid rows by groupby_col, computes the average of target_col,
    and flags any members whose target_col value deviates from the average by > threshold.
    Excludes rows where the groupby_col value is "NULL" or empty.
    """
    # Filter out empty or "NULL" group values
    filtered_df = valid_df[
        (valid_df[groupby_col] != "NULL") & 
        (valid_df[groupby_col] != "") & 
        (valid_df[groupby_col].notna())
    ].copy()

    # Determine group sizes
    group_counts = filtered_df[groupby_col].value_counts()
    eligible_groups = group_counts[group_counts >= min_members].index

    # Keep only members of eligible groups
    eligible_df = filtered_df[filtered_df[groupby_col].isin(eligible_groups)].copy()
    if eligible_df.empty:
        return {}

    # Compute group averages
    group_means = eligible_df.groupby(groupby_col)[target_col].mean()

    # Find deviations
    flags = {}
    for idx, row in eligible_df.iterrows():
        val = row[target_col]
        g_name = row[groupby_col]
        g_mean = group_means[g_name]
        diff = abs(val - g_mean)
        
        if diff > threshold:
            # We standardize the rule names to lowercase of groupby column name + _level_imbalance
            rule_name = f"{groupby_col.lower()}_level_imbalance"
            flags[idx] = {
                "rule": rule_name,
                "group_value": g_name,
                "idle_ratio": round(val, 4),
                "group_average": round(g_mean, 4),
                "deviation": round(diff, 4),
                "threshold": threshold
            }
            
    return flags

def check_group_imbalances(valid_df):
    """
    Applies the generic group analysis engine to Type, Site_ID, and Last_Operator_ID.
    Returns:
        merged_flags (dict): Map of original row index to list of group flags.
    """
    merged_flags = {}

    type_flags = analyze_group_imbalance(valid_df, "Type")
    site_flags = analyze_group_imbalance(valid_df, "Site_ID")
    op_flags = analyze_group_imbalance(valid_df, "Last_Operator_ID")

    all_indices = set(type_flags.keys()) | set(site_flags.keys()) | set(op_flags.keys())
    
    for idx in all_indices:
        merged_flags[idx] = []
        if idx in type_flags:
            merged_flags[idx].append(type_flags[idx])
        if idx in site_flags:
            merged_flags[idx].append(site_flags[idx])
        if idx in op_flags:
            merged_flags[idx].append(op_flags[idx])

    return merged_flags
