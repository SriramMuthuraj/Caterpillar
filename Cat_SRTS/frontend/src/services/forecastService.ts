import { apiClient } from './api';

/**
 * Phase detection, phase-end prediction and allocation.
 *
 * Served by the FastAPI half of the backend (backend/forecast). Shapes mirror
 * the API exactly — no renaming here, so a field that looks wrong on screen can
 * be traced straight to the endpoint that produced it.
 */

export type Verdict = 'ok' | 'insufficient_data';

export interface SitePhase {
  site_id: string;
  site_name: string;
  region: string;
  verdict: Verdict;
  reason: string | null;
  current_phase: string;
  /** What the classifier recovers from equipment mix alone. */
  detected_phase: string | null;
  detection_confidence: number | null;
  detection_agrees: boolean | null;
  phase_started_on: string;
  weeks_elapsed: number;
  /** null when the model refuses to predict for this phase. */
  weeks_remaining: number | null;
  weeks_remaining_low: number | null;
  weeks_remaining_high: number | null;
  phase_end_date: string | null;
  next_phase: string | null;
  next_phase_typical_weeks: number | null;
  machines_on_site: number;
}

export interface PhaseWindow {
  site_id: string;
  phase: string;
  phase_order: number;
  start_date: string;
  end_date: string | null;
  is_complete: boolean;
  start_censored: boolean;
  duration_weeks: number | null;
}

export interface PhaseTimeline {
  as_of: string;
  clock_source: string;
  phases: string[];
  sites: SitePhase[];
  windows: PhaseWindow[];
}

export interface AllocationOption {
  kind: 'redeploy' | 'rent';
  total_inr: number;
  available_on: string;
  wait_days: number;
  equipment_id?: string;
  from_site?: string;
  from_site_name?: string;
  distance_km?: number;
  haulage_inr?: number;
  waiting_inr?: number;
  extension_days?: number;
  extension_inr?: number;
  freed_because?: 'phase_ends' | 'contract_expires';
  hire_already_committed?: boolean;
  day_rate_inr?: number;
  days?: number;
  hire_inr?: number;
  mobilisation_inr?: number;
}

export interface Recommendation {
  site_id: string;
  site_name: string;
  type: string;
  quantity: number;
  needed_by: string;
  for_phase: string;
  decision: 'redeploy' | 'rent' | 'mixed';
  redeploy_count: number;
  rent_count: number;
  total_inr: number;
  all_rented_inr: number;
  saving_inr: number;
  rationale: string;
  redeployments: AllocationOption[];
  rentals: AllocationOption[];
}

export interface SurplusMachine {
  equipment_id: string;
  type: string;
  site_id: string;
  site_name: string;
  phase: string;
  check_out: string;
  freed_at: string;
  freed_because: 'phase_ends' | 'contract_expires';
  contract_days_left: number;
  surplus_days: number;
  idle_cost_inr: number;
  day_rate_inr: number;
}

export interface Allocation {
  as_of: string;
  clock_source: string;
  horizon_weeks: number;
  summary: {
    recommendations: number;
    redeploy: number;
    /** Rows that move some machines and rent the rest. */
    mixed: number;
    rent: number;
    machines_moved: number;
    /** Summed across every recommendation, including the mixed ones. */
    saving_inr: number;
    machines_running_past_need: number;
    idle_spend_inr: number;
  };
  recommendations: Recommendation[];
  surplus: SurplusMachine[];
  costing: Record<string, unknown>;
}

export interface PhaseModelReport {
  as_of: string;
  seed: number;
  n_sites: number;
  n_phase_windows: number;
  n_trainable_windows: number;
  n_panel_rows: number;
  classifier: {
    model: string;
    question: string;
    accuracy: number;
    within_one_phase: number;
    n_test_windows: number;
    per_phase_accuracy: Record<string, number>;
    feature_importance: Record<string, number>;
    method: string;
  };
  phase_end: {
    model: string;
    question: string;
    phases_refused: string[];
    mae_weeks: number;
    baseline_mae_weeks: number;
    skill_vs_baseline: number;
    interval_coverage: number;
    interval_level: number;
    interval_coverage_before_calibration: number;
    interval_pad_weeks: number;
    interval_method: string;
    mae_by_phase: Record<string, number>;
    feature_importance: Record<string, number>;
  };
  equipment_mix_by_phase: Record<string, Record<string, number>>;
}

export const forecastService = {
  async getTimeline(): Promise<PhaseTimeline> {
    const { data } = await apiClient.get<PhaseTimeline>('/api/phase/timeline');
    return data;
  },

  async getSite(siteId: string): Promise<SitePhase> {
    const { data } = await apiClient.get<SitePhase>(`/api/phase/${siteId}`);
    return data;
  },

  async getAllocation(): Promise<Allocation> {
    const { data } = await apiClient.get<Allocation>('/api/allocation');
    return data;
  },

  async getModelReport(): Promise<PhaseModelReport> {
    const { data } = await apiClient.get<PhaseModelReport>('/api/phase/model');
    return data;
  },
};

/** ₹1,478,366 -> "₹14.8L". Indian lakh/crore, because the rates are in INR. */
export const formatInr = (value: number): string => {
  const abs = Math.abs(value);
  if (abs >= 1e7) return `₹${(value / 1e7).toFixed(2)}Cr`;
  if (abs >= 1e5) return `₹${(value / 1e5).toFixed(1)}L`;
  if (abs >= 1e3) return `₹${(value / 1e3).toFixed(0)}k`;
  return `₹${Math.round(value)}`;
};

export const formatInrExact = (value: number): string =>
  `₹${Math.round(value).toLocaleString('en-IN')}`;
