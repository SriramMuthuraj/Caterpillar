import { apiClient } from './api';

/**
 * Anomaly findings.
 *
 * The rules live in `anomaly_detection/` and are untouched; the backend renames
 * the dataset on the way in and joins the project phase on the way out. The
 * phase is what turns "20% utilisation" into a judgement — unremarkable during
 * structural erection, alarming during earthworks.
 */

export type Severity = 'Critical' | 'Warning' | 'Normal';

export type FlagCategory =
  | 'integrity'
  | 'asset_rule'
  | 'self_baseline'
  | 'group'
  | 'unknown';

export interface AnomalyFlag {
  rule: string;
  category: FlagCategory;
  /** Rule-specific numbers: thresholds, means, deviations. */
  evidence: Record<string, unknown>;
}

export interface Finding {
  row_id: number;
  rental_id: string;
  equipment_id: string;
  type: string;
  site_id: string | null;
  phase: string | null;
  operator_id: string | null;
  check_in: string;
  check_out: string;
  engine_hours_per_day: number;
  idle_hours_per_day: number;
  utilisation: number | null;
  score: number;
  severity: Severity;
  is_valid_row: boolean;
  flags: AnomalyFlag[];
}

export interface AnomalySummary {
  as_of: string;
  clock_source: string;
  dataset_fingerprint: string;
  runtime_seconds: number;
  rows_scored: number;
  rows_flagged: number;
  machines_flagged: number;
  by_severity: Record<string, number>;
  by_rule: Record<string, number>;
  by_category: Record<string, number>;
  by_phase: Record<string, number>;
}

export interface AnomalyPage {
  as_of: string;
  total: number;
  limit: number;
  offset: number;
  findings: Finding[];
}

export interface AnomalyFilters {
  severity?: string;
  site_id?: string;
  type?: string;
  phase?: string;
  rule?: string;
  limit?: number;
  offset?: number;
}

export const anomalyService = {
  async getSummary(): Promise<AnomalySummary> {
    const { data } = await apiClient.get<AnomalySummary>('/api/anomalies/summary');
    return data;
  },

  async list(filters: AnomalyFilters = {}): Promise<AnomalyPage> {
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v !== undefined && v !== ''),
    );
    const { data } = await apiClient.get<AnomalyPage>('/api/anomalies', { params });
    return data;
  },

  async forEquipment(equipmentId: string) {
    const { data } = await apiClient.get(`/api/anomalies/${equipmentId}`);
    return data;
  },
};

/** Human labels. The rule ids are the API contract; these are for reading. */
export const RULE_LABELS: Record<string, string> = {
  impossible_hours: 'Impossible hours',
  bad_date_order: 'Check-out before check-in',
  zero_activity: 'No activity recorded',
  rental_days_mismatch: 'Stated days ≠ date span',
  booking_conflict: 'Double booked',
  unassigned_equipment: 'No site assigned',
  no_accountability: 'No operator named',
  under_utilized: 'Under-utilised',
  overdue: 'Overdue',
  self_baseline_deviation: 'Off its own baseline',
  type_level_imbalance: 'Outlier for its machine type',
  site_id_level_imbalance: 'Outlier for its site',
  last_operator_id_level_imbalance: 'Outlier for its operator',
};

export const CATEGORY_LABELS: Record<FlagCategory, string> = {
  integrity: 'Data integrity',
  asset_rule: 'Asset rule',
  self_baseline: 'Self baseline',
  group: 'Peer comparison',
  unknown: 'Other',
};

export const severityStyle = (severity: Severity) => {
  switch (severity) {
    case 'Critical':
      return 'bg-red-50 text-red-700 border-red-200';
    case 'Warning':
      return 'bg-amber-50 text-amber-700 border-amber-200';
    default:
      return 'bg-slate-50 text-slate-600 border-slate-200';
  }
};
