import React, { useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  ShieldAlert,
  Siren,
  Wrench,
} from 'lucide-react';

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { PageHeader } from '../components/ui/PageHeader';
import { MetricCard } from '../components/ui/MetricCard';
import { SearchInput } from '../components/ui/SearchInput';
import {
  anomalyService,
  CATEGORY_LABELS,
  Finding,
  IdleRatioGroup,
  RULE_LABELS,
  severityStyle,
} from '../services/anomalyService';

const PAGE_SIZE = 50;

/** Operators run to ~190 groups; the rest are small enough to chart whole. */
const OPERATOR_BARS = 15;

const CHARTS: { group: IdleRatioGroup; title: string; axis: string; limit?: number }[] = [
  { group: 'type', title: 'By equipment type', axis: 'Machine type' },
  { group: 'site', title: 'By site', axis: 'Site' },
  { group: 'operator', title: 'By operator', axis: 'Operator', limit: OPERATOR_BARS },
];

const label = (rule: string) => RULE_LABELS[rule] ?? rule.replace(/_/g, ' ');

/** Hold a value still until the user stops typing. */
const useDebounced = (value: string, ms: number) => {
  const [settled, setSettled] = useState(value);
  React.useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
};

/**
 * Average idle ratio for one grouping.
 *
 * Grey bars are groups the detector's imbalance rules never compared — fewer
 * than `min_group_members` rows, so there is no peer set. Showing them greyed
 * rather than hiding them is the point: a machine type with two rentals looks
 * like an outlier precisely because nothing was there to check it against.
 */
const IdleRatioChart: React.FC<{
  group: IdleRatioGroup;
  title: string;
  axis: string;
  limit?: number;
}> = ({ group, title, axis, limit }) => {
  const report = useQuery({
    queryKey: ['idle-ratio', group, limit],
    queryFn: () => anomalyService.idleRatio(group, limit),
  });

  const data = report.data;
  const bars = data?.groups ?? [];
  const truncated = data && limit ? data.total_groups > bars.length : false;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-4">
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <h3 className="text-sm font-bold text-slate-800">{title}</h3>
        <span className="text-[10px] font-semibold text-slate-400 whitespace-nowrap">
          {!data
            ? '…'
            : truncated
              ? `worst ${bars.length} of ${data.total_groups}`
              : `${data.total_groups} groups`}
        </span>
      </div>
      <p className="text-[11px] text-slate-400 mb-3">
        Idle ÷ (idle + engine), averaged over valid rentals
      </p>

      {report.isError ? (
        <p className="text-xs text-red-600 py-8 text-center">Could not load {axis} averages.</p>
      ) : (
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bars} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
              <XAxis
                dataKey="group"
                tick={{ fontSize: 9, fill: '#64748B' }}
                interval={0}
                angle={-40}
                textAnchor="end"
                height={58}
              />
              <YAxis
                tick={{ fontSize: 10, fill: '#64748B' }}
                tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
              />
              <Tooltip
                cursor={{ fill: '#F8FAFC' }}
                contentStyle={{
                  backgroundColor: '#ffffff',
                  borderRadius: '12px',
                  borderColor: '#F1F5F9',
                  fontSize: '12px',
                }}
                formatter={(value: number, _name, entry) => [
                  `${(value * 100).toFixed(1)}%  (n=${entry?.payload?.n}${
                    entry?.payload?.compared_by_rules ? '' : ', too few to compare'
                  })`,
                  'Avg idle',
                ]}
              />
              <Bar dataKey="idle_ratio" radius={[4, 4, 0, 0]}>
                {bars.map((bar) => (
                  <Cell
                    key={bar.group}
                    fill={bar.compared_by_rules ? '#2563EB' : '#CBD5E1'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

/** Rule evidence, rendered as-is. The numbers are the explanation. */
const Evidence: React.FC<{ evidence: Record<string, unknown> }> = ({ evidence }) => (
  <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-1 mt-1.5">
    {Object.entries(evidence).map(([key, value]) => (
      <div key={key} className="flex justify-between gap-2 text-[11px]">
        <dt className="text-slate-400 capitalize truncate">
          {key.replace(/_/g, ' ')}
        </dt>
        <dd className="font-semibold text-slate-700 whitespace-nowrap">
          {typeof value === 'number' ? Number(value.toFixed(4)) : String(value)}
        </dd>
      </div>
    ))}
  </dl>
);

const FindingRow: React.FC<{ finding: Finding }> = ({ finding }) => {
  const [open, setOpen] = useState(false);

  return (
    <>
      <tr
        className="border-b border-slate-100 hover:bg-slate-50/60 cursor-pointer"
        onClick={() => setOpen(!open)}
      >
        <td className="py-2.5 pl-4 pr-2 w-6 text-slate-300">
          {open ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </td>
        <td className="py-2.5 pr-3">
          <p className="text-sm font-semibold text-slate-800">
            {finding.equipment_id}
          </p>
          <p className="text-[11px] text-slate-400">{finding.type}</p>
        </td>
        <td className="py-2.5 pr-3 text-xs text-slate-600 whitespace-nowrap">
          {finding.site_id ?? (
            <span className="text-amber-600 font-semibold">unassigned</span>
          )}
        </td>
        <td className="py-2.5 pr-3">
          <span className="text-[11px] text-slate-600 capitalize">
            {finding.phase ?? '—'}
          </span>
        </td>
        <td className="py-2.5 pr-3 text-xs text-slate-500 whitespace-nowrap">
          {finding.utilisation != null
            ? `${(finding.utilisation * 100).toFixed(0)}%`
            : '—'}
        </td>
        <td className="py-2.5 pr-3">
          <div className="flex flex-wrap gap-1">
            {finding.flags.slice(0, 2).map((flag) => (
              <span
                key={flag.rule}
                className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600 whitespace-nowrap"
              >
                {label(flag.rule)}
              </span>
            ))}
            {finding.flags.length > 2 && (
              <span className="px-1.5 py-0.5 text-[10px] text-slate-400">
                +{finding.flags.length - 2}
              </span>
            )}
          </div>
        </td>
        <td className="py-2.5 pr-3 text-right text-sm font-bold text-slate-700">
          {finding.score}
        </td>
        <td className="py-2.5 pr-4 text-right">
          <span
            className={`inline-flex px-2 py-0.5 rounded-md text-[10px] font-bold border uppercase tracking-wide ${severityStyle(finding.severity)}`}
          >
            {finding.severity}
          </span>
        </td>
      </tr>

      {open && (
        <tr className="bg-slate-50/70">
          <td />
          <td colSpan={7} className="px-3 py-3">
            <p className="text-[11px] text-slate-500 mb-3">
              Rental {finding.rental_id} · {finding.check_in} → {finding.check_out} ·{' '}
              {finding.engine_hours_per_day}h working, {finding.idle_hours_per_day}h
              idle per day
              {finding.operator_id ? (
                <> · operator {finding.operator_id}</>
              ) : (
                <span className="text-amber-600 font-semibold"> · no operator named</span>
              )}
            </p>

            <div className="space-y-2">
              {finding.flags.map((flag) => (
                <div
                  key={flag.rule}
                  className="bg-white rounded-lg border border-slate-100 px-3 py-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-slate-700">
                      {label(flag.rule)}
                    </span>
                    <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">
                      {CATEGORY_LABELS[flag.category]}
                    </span>
                  </div>
                  <Evidence evidence={flag.evidence} />
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
};

export const AnomaliesPage: React.FC = () => {
  const [severity, setSeverity] = useState('');
  const [rule, setRule] = useState('');
  const [phase, setPhase] = useState('');
  const [siteId, setSiteId] = useState('');
  const [machine, setMachine] = useState('');
  const [page, setPage] = useState(0);

  // Typing straight into the query key would refetch on every keystroke.
  const search = useDebounced(machine, 300);

  const summary = useQuery({
    queryKey: ['anomaly-summary'],
    queryFn: anomalyService.getSummary,
  });

  const facets = useQuery({
    queryKey: ['anomaly-facets'],
    queryFn: anomalyService.facets,
  });

  const findings = useQuery({
    queryKey: ['anomalies', severity, rule, phase, siteId, search, page],
    queryFn: () =>
      anomalyService.list({
        severity: severity || undefined,
        rule: rule || undefined,
        phase: phase || undefined,
        site_id: siteId || undefined,
        equipment_id: search || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });

  const reset = (fn: (v: string) => void) => (value: string) => {
    fn(value);
    setPage(0);
  };

  React.useEffect(() => setPage(0), [search]);

  if (summary.isError) {
    return (
      <div className="p-8">
        <p className="text-sm font-semibold text-red-600">
          Could not reach the anomaly service.
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Start it with{' '}
          <code className="font-mono">uvicorn backend.main:app --port 8000</code>.
        </p>
      </div>
    );
  }

  const s = summary.data;
  const total = findings.data?.total ?? 0;
  const pages = Math.ceil(total / PAGE_SIZE);

  return (
    <div>
      <PageHeader
        title="Anomaly Detection"
        description={
          s
            ? `${s.rows_scored.toLocaleString()} rentals scored across ${s.machines_flagged} flagged machines. As of ${s.as_of}.`
            : 'Scoring the fleet history…'
        }
      />

      {s && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
          <MetricCard
            title="Critical"
            value={s.by_severity.Critical ?? 0}
            subtext="score ≥ 6"
            icon={Siren}
            badge={{ text: 'act now', variant: 'danger' }}
          />
          <MetricCard
            title="Warning"
            value={s.by_severity.Warning ?? 0}
            subtext="score ≥ 3"
            icon={AlertTriangle}
            badge={{ text: 'review', variant: 'warning' }}
          />
          <MetricCard
            title="Rows flagged"
            value={s.rows_flagged.toLocaleString()}
            subtext={`of ${s.rows_scored.toLocaleString()} scored`}
            icon={ShieldAlert}
          />
          <MetricCard
            title="Data integrity"
            value={s.by_category.integrity ?? 0}
            subtext="records that cannot be trusted"
            icon={Wrench}
          />
        </div>
      )}

      {/* Idle ratio by peer group */}
      <div className="grid gap-4 lg:grid-cols-3 mb-6">
        {CHARTS.map((chart) => (
          <IdleRatioChart key={chart.group} {...chart} />
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-4 mb-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
              Severity
            </label>
            <select
              value={severity}
              onChange={(e) => reset(setSeverity)(e.target.value)}
              className="w-full text-xs border border-slate-200 rounded-lg px-2.5 py-2 bg-white text-slate-700"
            >
              <option value="">All</option>
              <option value="Critical">Critical</option>
              <option value="Warning">Warning</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
              Rule
            </label>
            <select
              value={rule}
              onChange={(e) => reset(setRule)(e.target.value)}
              className="w-full text-xs border border-slate-200 rounded-lg px-2.5 py-2 bg-white text-slate-700"
            >
              <option value="">All rules</option>
              {s &&
                Object.entries(s.by_rule).map(([id, count]) => (
                  <option key={id} value={id}>
                    {label(id)} ({count})
                  </option>
                ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
              Project phase
            </label>
            <select
              value={phase}
              onChange={(e) => reset(setPhase)(e.target.value)}
              className="w-full text-xs border border-slate-200 rounded-lg px-2.5 py-2 bg-white text-slate-700 capitalize"
            >
              <option value="">All phases</option>
              {s &&
                Object.entries(s.by_phase)
                  .filter(([id]) => id !== 'unassigned')
                  .map(([id, count]) => (
                    <option key={id} value={id}>
                      {id} ({count})
                    </option>
                  ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
              Site
            </label>
            <select
              value={siteId}
              onChange={(e) => reset(setSiteId)(e.target.value)}
              className="w-full text-xs border border-slate-200 rounded-lg px-2.5 py-2 bg-white text-slate-700"
            >
              <option value="">All sites</option>
              {facets.data?.sites.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
              Equipment
            </label>
            <SearchInput
              value={machine}
              onChange={setMachine}
              placeholder="Machine id, e.g. EQX2484"
            />
          </div>
        </div>

        <p className="mt-3 text-[11px] text-slate-400 leading-snug">
          Peers are compared within machine type, site and operator. The project
          phase is shown alongside because 20% utilisation is unremarkable during
          erection and alarming during excavation — the rule cannot tell you
          which, but the phase can.
        </p>
      </div>

      {/* Findings */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px]">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                <th />
                {['Machine', 'Site', 'Phase', 'Util', 'Findings'].map((h) => (
                  <th
                    key={h}
                    className="py-2.5 pr-3 text-left text-[10px] font-bold uppercase tracking-wider text-slate-400"
                  >
                    {h}
                  </th>
                ))}
                <th className="py-2.5 pr-3 text-right text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Score
                </th>
                <th className="py-2.5 pr-4 text-right text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Severity
                </th>
              </tr>
            </thead>
            <tbody>
              {findings.isLoading && (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-xs text-slate-400">
                    Scoring…
                  </td>
                </tr>
              )}
              {findings.data?.findings.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-xs text-slate-400">
                    Nothing matches these filters.
                  </td>
                </tr>
              )}
              {findings.data?.findings.map((f) => (
                <FindingRow key={f.rental_id} finding={f} />
              ))}
            </tbody>
          </table>
        </div>

        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100">
            <p className="text-[11px] text-slate-400">
              {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of{' '}
              {total.toLocaleString()}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
                disabled={page >= pages - 1}
                className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
