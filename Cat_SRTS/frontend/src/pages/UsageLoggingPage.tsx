import React, { useState, useEffect } from 'react';
import { Gauge, Plus, Fuel, Clock, MapPin, User, Flame, TrendingUp } from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { MetricCard } from '../components/ui/MetricCard';
import { SearchInput } from '../components/ui/SearchInput';
import { Modal } from '../components/ui/Modal';
import { Toast, ToastMessage } from '../components/ui/Toast';
import { usageService } from '../services/usageService';
import { equipmentService } from '../services/equipmentService';
import { UsageLog, Equipment } from '../types';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts';

export const UsageLoggingPage: React.FC = () => {
  const [logs, setLogs] = useState<UsageLog[]>([]);
  const [equipmentList, setEquipmentList] = useState<Equipment[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const [toast, setToast] = useState<ToastMessage | null>(null);

  // New Log Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [logForm, setLogForm] = useState({
    equipmentId: '',
    equipmentName: '',
    date: new Date().toISOString().split('T')[0],
    runtimeHours: 8.0,
    fuelUsageLiters: 120,
    idleHours: 1.0,
    location: 'Apex Mine Site A',
    operatorName: 'Marcus Vance',
    efficiencyScore: 85,
  });

  const loadData = async () => {
    setLoading(true);
    const [usageList, eqList] = await Promise.all([usageService.getAll(), equipmentService.getAll()]);
    setLogs(usageList);
    setEquipmentList(eqList);
    setLoading(false);
  };

  useEffect(() => {
    loadData();
  }, []);

  const totalRuntime = logs.reduce((acc, curr) => acc + curr.runtimeHours, 0);
  const totalFuel = logs.reduce((acc, curr) => acc + curr.fuelUsageLiters, 0);
  const totalIdle = logs.reduce((acc, curr) => acc + curr.idleHours, 0);

  const handleOpenAdd = () => {
    const eq = equipmentList[0];
    setLogForm({
      equipmentId: eq ? eq.id : '',
      equipmentName: eq ? eq.name : '',
      date: new Date().toISOString().split('T')[0],
      runtimeHours: 8.0,
      fuelUsageLiters: 120,
      idleHours: 1.0,
      location: eq?.assignedSite || 'Apex Mine Site A',
      operatorName: eq?.assignedOperatorName || 'Marcus Vance',
      efficiencyScore: 85,
    });
    setIsModalOpen(true);
  };

  const handleEquipmentChange = (eqId: string) => {
    const eq = equipmentList.find((e) => e.id === eqId);
    if (eq) {
      setLogForm((prev) => ({
        ...prev,
        equipmentId: eq.id,
        equipmentName: eq.name,
        location: eq.assignedSite || prev.location,
        operatorName: eq.assignedOperatorName || prev.operatorName,
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await usageService.addLog(logForm);
    setToast({
      id: Date.now().toString(),
      type: 'success',
      title: 'Usage Logged',
      message: `Telematics usage entry added for ${logForm.equipmentName}.`,
    });
    setIsModalOpen(false);
    loadData();
  };

  const filteredLogs = logs.filter((log) => {
    const q = search.toLowerCase();
    return (
      log.equipmentName.toLowerCase().includes(q) ||
      log.equipmentId.toLowerCase().includes(q) ||
      log.location.toLowerCase().includes(q) ||
      log.operatorName.toLowerCase().includes(q)
    );
  });

  // Recharts transform data
  const chartData = logs.map((l) => ({
    name: l.equipmentName.split(' ')[1] + ' ' + l.equipmentName.split(' ')[2],
    Runtime: l.runtimeHours,
    Fuel: l.fuelUsageLiters,
    Idle: l.idleHours,
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Telematics & Usage Logging"
        description="Monitor runtime engine hours, fuel consumption liters, idle hours, and Caterpillar Product Link efficiency ratings."
        action={
          <button
            onClick={handleOpenAdd}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow-xs transition-colors"
          >
            <Plus className="w-4 h-4" />
            Log Manual Usage
          </button>
        }
      />

      {/* Summary Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Runtime Hours"
          value={`${totalRuntime.toFixed(1)} hrs`}
          subtext="Engine Operating Time"
          icon={Clock}
          badge={{ text: 'Productive Hours', variant: 'success' }}
        />
        <MetricCard
          title="Total Fuel Burned"
          value={`${totalFuel} L`}
          subtext="Diesel Fuel Consumed"
          icon={Fuel}
          badge={{ text: 'Liters Total', variant: 'info' }}
        />
        <MetricCard
          title="Total Idle Hours"
          value={`${totalIdle.toFixed(1)} hrs`}
          subtext="Non-productive Idle"
          icon={Gauge}
          badge={{ text: '18% Idle Ratio', variant: 'warning' }}
        />
        <MetricCard
          title="Avg Efficiency Score"
          value="84 %"
          subtext="Operator & Equipment Score"
          icon={TrendingUp}
          badge={{ text: 'Optimal', variant: 'success' }}
        />
      </div>

      {/* Recharts Visualization */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs">
          <h3 className="text-sm font-bold text-gray-900 mb-1">Runtime vs Idle Hours per Equipment</h3>
          <p className="text-xs text-gray-500 mb-4">Productive operation vs engine idling hours</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748B' }} />
                <YAxis tick={{ fontSize: 10, fill: '#64748B' }} />
                <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', fontSize: '12px' }} />
                <Bar dataKey="Runtime" name="Runtime (hrs)" fill="#2563EB" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Idle" name="Idle (hrs)" fill="#F59E0B" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs">
          <h3 className="text-sm font-bold text-gray-900 mb-1">Fuel Usage Trend (Liters)</h3>
          <p className="text-xs text-gray-500 mb-4">Total diesel consumption across active equipment</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748B' }} />
                <YAxis tick={{ fontSize: 10, fill: '#64748B' }} />
                <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', fontSize: '12px' }} />
                <Line type="monotone" dataKey="Fuel" name="Fuel (Liters)" stroke="#EF4444" strokeWidth={2.5} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Usage Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <h2 className="text-xs font-bold text-gray-900 uppercase tracking-wider">Telematics Usage Logs</h2>
          <div className="w-full sm:w-72">
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="Search by equipment, location or operator..."
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-500 uppercase text-[10px] tracking-wider border-b border-gray-200">
              <tr>
                <th className="px-4 py-3.5 font-bold">Log ID & Date</th>
                <th className="px-4 py-3.5 font-bold">Equipment</th>
                <th className="px-4 py-3.5 font-bold">Runtime Hours</th>
                <th className="px-4 py-3.5 font-bold">Fuel Used</th>
                <th className="px-4 py-3.5 font-bold">Idle Hours</th>
                <th className="px-4 py-3.5 font-bold">Location Site</th>
                <th className="px-4 py-3.5 font-bold">Operator</th>
                <th className="px-4 py-3.5 font-bold text-right">Efficiency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-gray-500">
                    Loading usage telematics...
                  </td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-12 text-center text-gray-500">
                    No telematics logs matched your query.
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50/80 transition-colors">
                    <td className="px-4 py-3.5">
                      <div className="font-mono font-bold text-blue-600">{log.id}</div>
                      <div className="text-[10px] text-gray-400">{log.date}</div>
                    </td>
                    <td className="px-4 py-3.5 font-bold text-gray-900">{log.equipmentName}</td>
                    <td className="px-4 py-3.5 font-semibold text-gray-900">{log.runtimeHours} hrs</td>
                    <td className="px-4 py-3.5 text-red-600 font-semibold">{log.fuelUsageLiters} L</td>
                    <td className="px-4 py-3.5 text-amber-600 font-medium">{log.idleHours} hrs</td>
                    <td className="px-4 py-3.5 text-gray-700">
                      <div className="flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-gray-400" />
                        {log.location}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-gray-800 font-medium">{log.operatorName}</td>
                    <td className="px-4 py-3.5 text-right font-bold">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[11px] ${
                          log.efficiencyScore >= 80
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}
                      >
                        {log.efficiencyScore}%
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Manual Usage Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Log Equipment Usage Entry">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Equipment</label>
              <select
                value={logForm.equipmentId}
                onChange={(e) => handleEquipmentChange(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
              >
                {equipmentList.map((eq) => (
                  <option key={eq.id} value={eq.id}>
                    {eq.name} ({eq.id})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Date</label>
              <input
                type="date"
                required
                value={logForm.date}
                onChange={(e) => setLogForm({ ...logForm, date: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Runtime Hours</label>
              <input
                type="number"
                step="0.1"
                required
                value={logForm.runtimeHours}
                onChange={(e) => setLogForm({ ...logForm, runtimeHours: Number(e.target.value) })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Fuel Used (Liters)</label>
              <input
                type="number"
                step="1"
                required
                value={logForm.fuelUsageLiters}
                onChange={(e) => setLogForm({ ...logForm, fuelUsageLiters: Number(e.target.value) })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Idle Hours</label>
              <input
                type="number"
                step="0.1"
                required
                value={logForm.idleHours}
                onChange={(e) => setLogForm({ ...logForm, idleHours: Number(e.target.value) })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Location Site</label>
              <input
                type="text"
                required
                value={logForm.location}
                onChange={(e) => setLogForm({ ...logForm, location: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>
          </div>

          <div className="pt-4 border-t border-gray-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="px-4 py-2 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700"
            >
              Submit Log
            </button>
          </div>
        </form>
      </Modal>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
};
