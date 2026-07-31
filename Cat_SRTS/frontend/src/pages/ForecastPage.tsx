import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  IndianRupee,
  Layers,
  MapPin,
  TrendingDown,
  Truck,
} from 'lucide-react';

import { PageHeader } from '../components/ui/PageHeader';
import { MetricCard } from '../components/ui/MetricCard';
import {
  forecastService,
  formatInr,
  formatInrExact,
  Recommendation,
  SitePhase,
} from '../services/forecastService';

const PHASE_ORDER = [
  'clearing',
  'excavation',
  'foundation',
  'erection',
  'grading',
  'demobilisation',
];

const PHASE_COLOUR: Record<string, string> = {
  clearing: 'bg-lime-100 text-lime-800 border-lime-200',
  excavation: 'bg-amber-100 text-amber-800 border-amber-200',
  foundation: 'bg-orange-100 text-orange-800 border-orange-200',
  erection: 'bg-blue-100 text-blue-800 border-blue-200',
  grading: 'bg-violet-100 text-violet-800 border-violet-200',
  demobilisation: 'bg-slate-100 text-slate-700 border-slate-200',
};

const PhaseChip: React.FC<{ phase: string | null }> = ({ phase }) => (
  <span
    className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border capitalize ${
      (phase && PHASE_COLOUR[phase]) || 'bg-slate-100 text-slate-600 border-slate-200'
    }`}
  >
    {phase ?? 'unknown'}
  </span>
);

/**
 * The prediction interval, drawn.
 *
 * A bare "4 weeks" claims a precision nobody has. The bar shows P10-P90 with
 * the median marked, so the width of the uncertainty is as visible as the
 * estimate — which is the whole reason the model emits quantiles.
 */
const RangeBar: React.FC<{ low: number; mid: number; high: number }> = ({
  low,
  mid,
  high,
}) => {
  const span = Math.max(high, 1);
  const leftPct = Math.max(0, (low / span) * 100);
  const widthPct = Math.max(2, ((high - low) / span) * 100);
  const midPct = Math.min(99, (mid / span) * 100);

  return (
    <div className="mt-2">
      <div className="relative h-2 rounded-full bg-slate-100">
        <div
          className="absolute h-2 rounded-full bg-blue-200"
          style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
        />
        <div
          className="absolute -top-0.5 w-0.5 h-3 bg-blue-700 rounded"
          style={{ left: `${midPct}%` }}
        />
      </div>
      <div className="flex justify-between mt-1 text-[10px] text-slate-400 font-medium">
        <span>{low.toFixed(1)}w</span>
        <span className="text-blue-700 font-bold">{mid.toFixed(1)}w</span>
        <span>{high.toFixed(1)}w</span>
      </div>
    </div>
  );
};

const SiteCard: React.FC<{ site: SitePhase }> = ({ site }) => {
  const refused = site.verdict === 'insufficient_data' || site.weeks_remaining === null;

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-100 hover:border-slate-200 transition-all">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-bold text-slate-800 truncate">{site.site_name}</p>
          <p className="text-[11px] text-slate-400 font-medium">
            {site.site_id} · {site.region} · {site.machines_on_site} machines
          </p>
        </div>
        <PhaseChip phase={site.current_phase} />
      </div>

      {/* Whether the classifier independently recovers the same phase from the
          equipment on the ground. Disagreement is worth seeing, not hiding. */}
      {site.detected_phase && (
        <p className="mt-2 text-[11px] text-slate-500">
          {site.detection_agrees ? (
            <span className="text-emerald-600 font-medium">
              ✓ detector agrees
              {site.detection_confidence != null &&
                ` (${(site.detection_confidence * 100).toFixed(0)}% confident)`}
            </span>
          ) : (
            <span className="text-amber-600 font-medium">
              detector reads “{site.detected_phase}”
            </span>
          )}
        </p>
      )}

      <div className="mt-3 pt-3 border-t border-slate-100">
        {refused ? (
          <>
            <p className="text-xs font-semibold text-slate-500">
              No end date predicted
            </p>
            <p className="mt-1 text-[11px] text-slate-400 leading-snug">
              {site.reason ??
                'Too few completed phases of this kind to predict from. Refusing is the correct answer.'}
            </p>
          </>
        ) : (
          <>
            <div className="flex items-baseline justify-between">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                Ends in
              </span>
              <span className="text-xs text-slate-500 font-medium">
                {site.phase_end_date}
              </span>
            </div>
            <RangeBar
              low={site.weeks_remaining_low ?? 0}
              mid={site.weeks_remaining ?? 0}
              high={site.weeks_remaining_high ?? 0}
            />
          </>
        )}
      </div>

      {site.next_phase && (
        <div className="mt-3 pt-3 border-t border-slate-100 flex items-center gap-2 text-[11px]">
          <span className="text-slate-400 font-medium">next</span>
          <ArrowRight className="w-3 h-3 text-slate-300" />
          <PhaseChip phase={site.next_phase} />
          {site.next_phase_typical_weeks != null && (
            <span className="text-slate-400">
              ~{site.next_phase_typical_weeks.toFixed(0)}w
            </span>
          )}
        </div>
      )}
    </div>
  );
};

const DecisionRow: React.FC<{ rec: Recommendation }> = ({ rec }) => {
  const [open, setOpen] = useState(false);

  const decisionStyle =
    rec.decision === 'redeploy'
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : rec.decision === 'rent'
        ? 'bg-blue-50 text-blue-700 border-blue-200'
        : 'bg-violet-50 text-violet-700 border-violet-200';

  return (
    <>
      <tr
        className="border-b border-slate-100 hover:bg-slate-50/60 cursor-pointer"
        onClick={() => setOpen(!open)}
      >
        <td className="py-3 pl-4 pr-2 w-6 text-slate-300">
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </td>
        <td className="py-3 pr-3">
          <p className="text-sm font-semibold text-slate-800">{rec.site_name}</p>
          <p className="text-[11px] text-slate-400">{rec.site_id}</p>
        </td>
        <td className="py-3 pr-3 text-sm text-slate-700 whitespace-nowrap">
          {rec.quantity} × {rec.type}
        </td>
        <td className="py-3 pr-3">
          <PhaseChip phase={rec.for_phase} />
        </td>
        <td className="py-3 pr-3">
          <span
            className={`inline-flex px-2 py-0.5 rounded-md text-[11px] font-bold border uppercase tracking-wide ${decisionStyle}`}
          >
            {rec.decision === 'mixed'
              ? `${rec.redeploy_count} move · ${rec.rent_count} rent`
              : rec.decision}
          </span>
        </td>
        <td className="py-3 pr-3 text-right text-sm font-semibold text-slate-800 whitespace-nowrap">
          {formatInr(rec.total_inr)}
        </td>
        <td className="py-3 pr-4 text-right whitespace-nowrap">
          {rec.saving_inr > 0 ? (
            <span className="text-sm font-bold text-emerald-600">
              −{formatInr(rec.saving_inr)}
            </span>
          ) : (
            <span className="text-xs text-slate-300">—</span>
          )}
        </td>
      </tr>

      {open && (
        <tr className="bg-slate-50/70">
          <td />
          <td colSpan={6} className="px-3 py-4">
            <p className="text-xs text-slate-600 leading-relaxed max-w-3xl">
              {rec.rationale}
            </p>

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              {/* Both prices, side by side. The point is that the choice can be
                  checked rather than trusted. */}
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 mb-2">
                  Move ({rec.redeployments.length})
                </p>
                {rec.redeployments.length === 0 ? (
                  <p className="text-xs text-slate-400">
                    Nothing spare within reach.
                  </p>
                ) : (
                  <ul className="space-y-1.5">
                    {rec.redeployments.map((o) => (
                      <li
                        key={o.equipment_id}
                        className="text-xs bg-white rounded-lg border border-slate-100 px-3 py-2"
                      >
                        <div className="flex justify-between gap-2">
                          <span className="font-semibold text-slate-700">
                            {o.equipment_id}
                          </span>
                          <span className="font-semibold text-slate-800">
                            {formatInrExact(o.total_inr)}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          from {o.from_site_name} · {o.distance_km?.toFixed(0)} km ·
                          free {o.available_on} ({o.wait_days}d wait)
                        </p>
                        <p className="text-[10px] text-slate-400 mt-0.5">
                          {o.freed_because === 'phase_ends'
                            ? 'its phase finishes'
                            : 'its contract expires'}
                          {o.hire_already_committed && ' · hire already paid for'}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-blue-700 mb-2">
                  Rent ({rec.rentals.length})
                </p>
                {rec.rentals.length === 0 ? (
                  <p className="text-xs text-slate-400">Nothing needs renting.</p>
                ) : (
                  <div className="text-xs bg-white rounded-lg border border-slate-100 px-3 py-2">
                    <div className="flex justify-between gap-2">
                      <span className="font-semibold text-slate-700">
                        {rec.rentals.length} × {rec.type}
                      </span>
                      <span className="font-semibold text-slate-800">
                        {formatInrExact(
                          rec.rentals.reduce((s, o) => s + o.total_inr, 0),
                        )}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      {formatInrExact(rec.rentals[0].day_rate_inr ?? 0)}/day ×{' '}
                      {rec.rentals[0].days} days + mobilisation, available
                      immediately
                    </p>
                  </div>
                )}
              </div>
            </div>

            <p className="mt-3 text-[11px] text-slate-400">
              Renting all {rec.quantity}: {formatInrExact(rec.all_rented_inr)} ·
              chosen plan: {formatInrExact(rec.total_inr)}
            </p>
          </td>
        </tr>
      )}
    </>
  );
};

const EvidencePanel: React.FC = () => {
  const [open, setOpen] = useState(false);
  const { data } = useQuery({
    queryKey: ['phase-model'],
    queryFn: forecastService.getModelReport,
    enabled: open,
  });

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-100 mb-6">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3.5 text-left"
      >
        <div className="flex items-center gap-2.5">
          <Activity className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-semibold text-slate-700">
            How well do these models actually do?
          </span>
        </div>
        {open ? (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-slate-400" />
        )}
      </button>

      {open && data && (
        <div className="px-5 pb-5 border-t border-slate-100 pt-4 grid gap-6 md:grid-cols-2">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
              Phase detection · {data.classifier.model}
            </p>
            <dl className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <dt className="text-slate-500">Accuracy</dt>
                <dd className="font-bold text-slate-800">
                  {(data.classifier.accuracy * 100).toFixed(1)}%
                  <span className="ml-1.5 font-normal text-slate-400">
                    vs 16.7% chance
                  </span>
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Within one phase</dt>
                <dd className="font-bold text-slate-800">
                  {(data.classifier.within_one_phase * 100).toFixed(1)}%
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Held-out windows</dt>
                <dd className="font-bold text-slate-800">
                  {data.classifier.n_test_windows}
                </dd>
              </div>
            </dl>
            <p className="mt-2 text-[11px] text-slate-400 leading-snug">
              {data.classifier.method}
            </p>
          </div>

          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
              Phase end · {data.phase_end.model}
            </p>
            <dl className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <dt className="text-slate-500">Error</dt>
                <dd className="font-bold text-slate-800">
                  {data.phase_end.mae_weeks.toFixed(2)} weeks
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Baseline</dt>
                <dd className="font-medium text-slate-600">
                  {data.phase_end.baseline_mae_weeks.toFixed(2)} weeks
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Skill</dt>
                <dd className="font-bold text-emerald-600">
                  {(data.phase_end.skill_vs_baseline * 100).toFixed(1)}%
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">
                  Coverage @ {(data.phase_end.interval_level * 100).toFixed(0)}%
                </dt>
                <dd className="font-bold text-slate-800">
                  {(data.phase_end.interval_coverage * 100).toFixed(1)}%
                  <span className="ml-1.5 font-normal text-slate-400">
                    (raw{' '}
                    {(
                      data.phase_end.interval_coverage_before_calibration * 100
                    ).toFixed(0)}
                    %)
                  </span>
                </dd>
              </div>
            </dl>
            {data.phase_end.phases_refused.length > 0 && (
              <p className="mt-2 text-[11px] text-slate-400 leading-snug">
                Refuses to predict: {data.phase_end.phases_refused.join(', ')} — too
                few completed observations.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export const ForecastPage: React.FC = () => {
  const timeline = useQuery({
    queryKey: ['phase-timeline'],
    queryFn: forecastService.getTimeline,
  });
  const allocation = useQuery({
    queryKey: ['allocation'],
    queryFn: forecastService.getAllocation,
  });

  const [phaseFilter, setPhaseFilter] = useState<string>('');

  if (timeline.isLoading || allocation.isLoading) {
    return (
      <div className="p-8 text-center text-sm text-slate-400">
        Building the forecast…
      </div>
    );
  }

  if (timeline.isError || allocation.isError) {
    return (
      <div className="p-8">
        <p className="text-sm font-semibold text-red-600">
          Could not reach the forecast service.
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Start it with <code className="font-mono">uvicorn backend.main:app --port 8000</code>.
        </p>
      </div>
    );
  }

  const sites = timeline.data!.sites;
  const alloc = allocation.data!;
  const visible = phaseFilter
    ? sites.filter((s) => s.current_phase === phaseFilter)
    : sites;

  return (
    <div>
      <PageHeader
        title="Demand Forecast"
        description={`What phase each site is in, when it ends, and what to do about the machines. As of ${timeline.data!.as_of}.`}
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
        <MetricCard
          title="Active sites"
          value={sites.length}
          subtext={`${alloc.horizon_weeks}-week horizon`}
          icon={MapPin}
        />
        <MetricCard
          title="Recommendations"
          value={alloc.summary.recommendations}
          subtext={`${alloc.summary.redeploy} move · ${alloc.summary.rent} rent`}
          icon={Truck}
        />
        <MetricCard
          title="Saving available"
          value={formatInr(alloc.summary.saving_inr)}
          subtext="vs renting everything"
          icon={IndianRupee}
          badge={{ text: 'moving beats renting', variant: 'success' }}
        />
        <MetricCard
          title="Running past need"
          value={alloc.summary.machines_running_past_need}
          subtext={`${formatInr(alloc.summary.idle_spend_inr)} of idle hire`}
          icon={TrendingDown}
          badge={{ text: 'recoverable', variant: 'warning' }}
        />
      </div>

      <EvidencePanel />

      {/* Phase board */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold text-slate-700 flex items-center gap-2">
          <Layers className="w-4 h-4 text-slate-400" />
          Site phases
        </h2>
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setPhaseFilter('')}
            className={`px-2 py-1 rounded-md text-[11px] font-semibold border ${
              phaseFilter === ''
                ? 'bg-slate-800 text-white border-slate-800'
                : 'bg-white text-slate-500 border-slate-200 hover:border-slate-300'
            }`}
          >
            All {sites.length}
          </button>
          {PHASE_ORDER.map((phase) => {
            const count = sites.filter((s) => s.current_phase === phase).length;
            if (!count) return null;
            return (
              <button
                key={phase}
                onClick={() => setPhaseFilter(phase === phaseFilter ? '' : phase)}
                className={`px-2 py-1 rounded-md text-[11px] font-semibold border capitalize ${
                  phaseFilter === phase
                    ? 'bg-slate-800 text-white border-slate-800'
                    : 'bg-white text-slate-500 border-slate-200 hover:border-slate-300'
                }`}
              >
                {phase} {count}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 mb-8">
        {visible.map((site) => (
          <SiteCard key={site.site_id} site={site} />
        ))}
      </div>

      {/* Decision board */}
      <h2 className="text-sm font-bold text-slate-700 flex items-center gap-2 mb-3">
        <Truck className="w-4 h-4 text-slate-400" />
        Decision board
        <span className="font-normal text-slate-400">
          — move a machine you already pay for, or call off a new rental
        </span>
      </h2>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px]">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                <th />
                <th className="py-2.5 pr-3 text-left text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Site
                </th>
                <th className="py-2.5 pr-3 text-left text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Needs
                </th>
                <th className="py-2.5 pr-3 text-left text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  For phase
                </th>
                <th className="py-2.5 pr-3 text-left text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Decision
                </th>
                <th className="py-2.5 pr-3 text-right text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Cost
                </th>
                <th className="py-2.5 pr-4 text-right text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Saving
                </th>
              </tr>
            </thead>
            <tbody>
              {alloc.recommendations.map((rec) => (
                <DecisionRow key={`${rec.site_id}-${rec.type}`} rec={rec} />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="mt-3 text-[11px] text-slate-400">
        Redeployment does not pay hire — that contract is already running and the
        money is spent whether the machine works or sits. That asymmetry is why
        the answer is usually “move it”.
      </p>
    </div>
  );
};
