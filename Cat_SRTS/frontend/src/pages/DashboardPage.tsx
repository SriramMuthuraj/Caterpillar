import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Truck,
  Activity,
  AlertOctagon,
  UserCheck,
  CheckCircle2,
  PlusCircle,
  KeyRound,
  ChevronRight,
  TrendingUp,
  MapPin,
  ArrowUpRight,
  ArrowDownLeft,
  ShieldAlert,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { MetricCard } from '../components/ui/MetricCard';
import { StatusBadge } from '../components/ui/StatusBadge';
import { SearchInput } from '../components/ui/SearchInput';
import { Modal } from '../components/ui/Modal';
import { Toast, ToastMessage } from '../components/ui/Toast';
import { equipmentService } from '../services/equipmentService';
import { rentalService } from '../services/rentalService';
import { alertService } from '../services/alertService';
import { Equipment, RentalRecord, SystemAlert } from '../types';
import { INITIAL_ACTIVITIES } from '../mocks/data';
import { formatCurrency } from '../utils/formatters';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts';

export const DashboardPage: React.FC = () => {
  const [equipmentList, setEquipmentList] = useState<Equipment[]>([]);
  const [rentals, setRentals] = useState<RentalRecord[]>([]);
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [loading, setLoading] = useState(true);

  // Rental Operations State
  const [rentalTab, setRentalTab] = useState<'status' | 'activities' | 'history'>('status');
  const [rentalSearch, setRentalSearch] = useState('');
  const [rentalStatusFilter, setRentalStatusFilter] = useState('All');
  const [toast, setToast] = useState<ToastMessage | null>(null);

  // Check-Out Modal State
  const [isCheckOutOpen, setIsCheckOutOpen] = useState(false);
  const [checkOutForm, setCheckOutForm] = useState({
    equipmentId: '',
    equipmentName: '',
    dealerName: 'Empire Cat Equipment Dealer',
    startDate: new Date().toISOString().split('T')[0],
    expectedReturnDate: '2026-08-30',
    dailyRate: 450,
    operatorName: 'Marcus Vance',
    siteName: 'Apex Mine Site A',
  });

  // Check-In Modal State
  const [checkInRental, setCheckInRental] = useState<RentalRecord | null>(null);
  const [checkInDate, setCheckInDate] = useState(new Date().toISOString().split('T')[0]);

  const loadData = async () => {
    setLoading(true);
    const [eqData, rentalData, alertData] = await Promise.all([
      equipmentService.getAll(),
      rentalService.getAll(),
      alertService.getAll(),
    ]);
    // Filter out 'Returned' equipment from live equipment list for operational focus
    setEquipmentList(eqData.filter((e) => e.currentStatus !== 'Returned'));
    setRentals(rentalData);
    setAlerts(alertData);
    setLoading(false);
  };

  useEffect(() => {
    loadData();
  }, []);

  // Operational Equipment KPI Calculations (No Returned Assets)
  const totalEquipment = equipmentList.length;
  const activeEquipment = equipmentList.filter(
    (e) => e.currentStatus === 'Active' || e.currentStatus === 'Working'
  ).length;
  const inactiveEquipment = equipmentList.filter(
    (e) => e.currentStatus === 'Inactive' || e.currentStatus === 'Maintenance'
  ).length;
  const currentlyAssigned = equipmentList.filter(
    (e) => Boolean(e.assignedOperatorName) && e.assignedOperatorName !== 'Unassigned'
  ).length;
  const availableEquipment = equipmentList.filter(
    (e) => (!e.assignedOperatorName || e.assignedOperatorName === 'Unassigned') && e.currentStatus !== 'Maintenance'
  ).length;

  const idleEquipment = equipmentList.filter((e) => e.currentStatus === 'Idle').length;

  // Chart data focusing strictly on operational equipment
  const chartData = [
    { name: 'Active / Working', value: activeEquipment, color: '#22C55E' },
    { name: 'Idle Status', value: idleEquipment, color: '#F59E0B' },
    { name: 'Maintenance / Inactive', value: inactiveEquipment, color: '#EF4444' },
  ];

  const siteData = [
    { name: 'Apex Mine Site A', count: 3, hpAvg: 282 },
    { name: 'North Quarry Pit #3', count: 2, hpAvg: 226 },
    { name: 'Metro Transit Site', count: 1, hpAvg: 504 },
    { name: 'Sunrise Highway', count: 1, hpAvg: 157 },
  ];

  // Rental Operations Modal Handlers
  const handleOpenCheckOut = () => {
    const available = equipmentList.find((e) => e.ownership === 'Rental') || equipmentList[0];
    setCheckOutForm({
      equipmentId: available ? available.id : '',
      equipmentName: available ? available.name : '',
      dealerName: available?.dealerName || 'Empire Cat Equipment Dealer',
      startDate: new Date().toISOString().split('T')[0],
      expectedReturnDate: '2026-08-30',
      dailyRate: available?.dailyRate || 450,
      operatorName: 'Marcus Vance',
      siteName: 'Apex Mine Site A',
    });
    setIsCheckOutOpen(true);
  };

  const handleEquipmentSelect = (eqId: string) => {
    const eq = equipmentList.find((e) => e.id === eqId);
    if (eq) {
      setCheckOutForm((prev) => ({
        ...prev,
        equipmentId: eq.id,
        equipmentName: eq.name,
        dealerName: eq.dealerName || 'Empire Cat Equipment Dealer',
        dailyRate: eq.dailyRate || 450,
      }));
    }
  };

  const handleCheckOutSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const start = new Date(checkOutForm.startDate);
    const end = new Date(checkOutForm.expectedReturnDate);
    const diffDays = Math.max(1, Math.ceil((end.getTime() - start.getTime()) / (1000 * 3600 * 24)));
    const totalCost = diffDays * checkOutForm.dailyRate;

    await rentalService.checkOut({
      ...checkOutForm,
      totalCost,
    });

    setToast({
      id: Date.now().toString(),
      type: 'success',
      title: 'Rental Checked-Out',
      message: `${checkOutForm.equipmentName} successfully checked out from ${checkOutForm.dealerName}.`,
    });

    setIsCheckOutOpen(false);
    loadData();
  };

  const handleCheckInSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!checkInRental) return;

    await rentalService.checkIn(checkInRental.id, checkInDate);
    setToast({
      id: Date.now().toString(),
      type: 'success',
      title: 'Rental Checked-In',
      message: `${checkInRental.equipmentName} successfully checked in and returned.`,
    });

    setCheckInRental(null);
    loadData();
  };

  const filteredRentals = rentals.filter((r) => {
    const q = rentalSearch.toLowerCase();
    const matchesSearch =
      r.equipmentName.toLowerCase().includes(q) ||
      r.id.toLowerCase().includes(q) ||
      r.dealerName.toLowerCase().includes(q) ||
      r.siteName.toLowerCase().includes(q);
    const matchesStatus = rentalStatusFilter === 'All' || r.status === rentalStatusFilter;
    return matchesSearch && matchesStatus;
  });

  const activeRentals = rentals.filter((r) => r.status !== 'Returned');

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="Equipment Fleet Dashboard"
        description="Real-time operational overview, telematics deployment, and Caterpillar rental operations management."
        action={
          <Link
            to="/registration/equipment"
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow-xs transition-colors"
          >
            <PlusCircle className="w-4 h-4" />
            Register Equipment
          </Link>
        }
      />

      {/* 1. Operational KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard
          title="Total Equipment"
          value={totalEquipment}
          subtext="Owned & Active Rented"
          icon={Truck}
          badge={{ text: `${totalEquipment} Units`, variant: 'info' }}
        />
        <MetricCard
          title="Active Equipment"
          value={activeEquipment}
          subtext="Currently Deployed"
          icon={Activity}
          badge={{ text: `${Math.round((activeEquipment / (totalEquipment || 1)) * 100)}% Active`, variant: 'success' }}
        />
        <MetricCard
          title="Inactive Equipment"
          value={inactiveEquipment}
          subtext="Idle or Maintenance"
          icon={AlertOctagon}
          badge={{ text: `${inactiveEquipment} Units`, variant: 'warning' }}
        />
        <MetricCard
          title="Currently Assigned"
          value={currentlyAssigned}
          subtext="Assigned to Operators"
          icon={UserCheck}
          badge={{ text: 'In Field', variant: 'info' }}
        />
        <MetricCard
          title="Available Equipment"
          value={availableEquipment}
          subtext="Ready for Assignment"
          icon={CheckCircle2}
          badge={{ text: 'Ready', variant: 'success' }}
        />
      </div>

      {/* 2. Deployment Status Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Deployment Status Donut Chart */}
        <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold text-slate-800">Deployment Status Breakdown</h2>
              <span className="text-xs text-slate-400 font-medium">Operational Status</span>
            </div>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#ffffff', borderRadius: '12px', borderColor: '#F1F5F9', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-3 border-t border-slate-100">
            {chartData.map((item) => (
              <div key={item.name} className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
                <span className="text-xs text-slate-600 font-medium truncate">{item.name}:</span>
                <span className="text-xs font-bold text-slate-800">{item.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Site Deployment Bar Chart */}
        <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-slate-800">Equipment Distribution by Project Site</h2>
              <p className="text-xs text-slate-500 mt-0.5">Active equipment deployed per mining & construction location</p>
            </div>
            <span className="text-xs font-semibold text-blue-600 flex items-center gap-1 bg-blue-50 px-2.5 py-1 rounded-md border border-blue-100">
              <TrendingUp className="w-3.5 h-3.5" /> High Utilization
            </span>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={siteData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748B' }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748B' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#ffffff', borderRadius: '12px', borderColor: '#F1F5F9', fontSize: '12px' }}
                />
                <Bar dataKey="count" name="Equipment Count" fill="#2563EB" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* 3. Live Equipment Status */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-800">Live Equipment Status</h2>
            <p className="text-xs text-slate-500 mt-0.5">Real-time telematics status of registered operational equipment</p>
          </div>
          <Link
            to="/assets"
            className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
          >
            View All Assets <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-400 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
              <tr>
                <th className="px-4 py-3 font-bold">Equipment ID & Name</th>
                <th className="px-4 py-3 font-bold">Category</th>
                <th className="px-4 py-3 font-bold">Ownership</th>
                <th className="px-4 py-3 font-bold">Assigned Operator & Site</th>
                <th className="px-4 py-3 font-bold text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={5} className="p-6 text-center text-slate-400 font-medium">
                    Loading equipment dataset...
                  </td>
                </tr>
              ) : (
                equipmentList.slice(0, 5).map((eq) => (
                  <tr key={eq.id} className="hover:bg-slate-50/60 transition-colors text-slate-600">
                    <td className="px-4 py-3">
                      <div className="font-bold text-slate-800">{eq.name}</div>
                      <div className="text-[11px] text-slate-400 font-mono">{eq.id}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-600 font-medium">{eq.category}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          eq.ownership === 'Rental'
                            ? 'bg-amber-50 text-amber-700 border border-amber-100'
                            : 'bg-blue-50 text-blue-700 border border-blue-100'
                        }`}
                      >
                        {eq.ownership}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      <div className="font-semibold text-slate-800">{eq.assignedOperatorName || 'Unassigned'}</div>
                      <div className="text-[11px] text-slate-500 flex items-center gap-1 mt-0.5">
                        <MapPin className="w-3 h-3 text-slate-400" />
                        {eq.assignedSite || 'Central Depot'}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <StatusBadge status={eq.currentStatus} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 4. Rental Operations Section */}
      <div className="bg-white p-5 sm:p-6 rounded-2xl border border-slate-100 shadow-sm space-y-5">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <KeyRound className="w-5 h-5 text-blue-600" />
              <h2 className="text-lg font-bold text-slate-800">Rental Operations</h2>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Process Caterpillar dealer equipment check-outs, return check-ins, inspect active rental status, and preview contract history.
            </p>
          </div>

          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            <button
              onClick={handleOpenCheckOut}
              className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-blue-600 rounded-xl hover:bg-blue-700 shadow-xs transition-colors"
            >
              <ArrowUpRight className="w-4 h-4" />
              Check-Out Equipment
            </button>
            <button
              onClick={() => {
                if (activeRentals.length > 0) setCheckInRental(activeRentals[0]);
              }}
              className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-slate-700 bg-slate-100 rounded-xl hover:bg-slate-200 transition-colors"
            >
              <ArrowDownLeft className="w-4 h-4 text-emerald-600" />
              Check-In Return
            </button>
          </div>
        </div>

        {/* Tab Navigation & Controls */}
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-1.5 p-1 bg-slate-100 rounded-xl w-full md:w-auto">
            <button
              onClick={() => setRentalTab('status')}
              className={`flex-1 md:flex-none px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                rentalTab === 'status'
                  ? 'bg-white text-blue-700 shadow-2xs font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Current Rental Status ({activeRentals.length})
            </button>
            <button
              onClick={() => setRentalTab('activities')}
              className={`flex-1 md:flex-none px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                rentalTab === 'activities'
                  ? 'bg-white text-blue-700 shadow-2xs font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Recent Rental Activities
            </button>
            <button
              onClick={() => setRentalTab('history')}
              className={`flex-1 md:flex-none px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                rentalTab === 'history'
                  ? 'bg-white text-blue-700 shadow-2xs font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Rental History Preview
            </button>
          </div>

          {rentalTab === 'history' && (
            <div className="flex items-center gap-3 w-full md:w-auto">
              <div className="flex-1 md:w-64">
                <SearchInput
                  value={rentalSearch}
                  onChange={setRentalSearch}
                  placeholder="Search contract, dealer or site..."
                />
              </div>
              <select
                value={rentalStatusFilter}
                onChange={(e) => setRentalStatusFilter(e.target.value)}
                className="px-3 py-2 text-xs bg-white border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-400 text-slate-800"
              >
                <option value="All">All Statuses</option>
                <option value="Working">Working</option>
                <option value="Idle">Idle</option>
                <option value="Returned">Returned</option>
              </select>
            </div>
          )}
        </div>

        {/* Tab 1: Current Rental Status */}
        {rentalTab === 'status' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-2">
            {activeRentals.length === 0 ? (
              <div className="col-span-full text-center py-8 text-slate-400 text-xs font-medium">
                No active rental contracts in progress. Click "Check-Out Equipment" to issue a contract.
              </div>
            ) : (
              activeRentals.map((r) => (
                <div key={r.id} className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 flex flex-col justify-between space-y-3 hover:border-slate-300 transition-colors">
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-blue-600 text-xs">{r.id}</span>
                      <StatusBadge status={r.status} />
                    </div>
                    <h3 className="font-bold text-slate-800 text-sm mt-1">{r.equipmentName}</h3>
                    <p className="text-[11px] text-slate-500">{r.dealerName}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-[11px] pt-2 border-t border-slate-100">
                    <div>
                      <p className="text-slate-400 font-medium">Site Location</p>
                      <p className="font-semibold text-slate-700 truncate">{r.siteName}</p>
                    </div>
                    <div>
                      <p className="text-slate-400 font-medium">Daily Rate</p>
                      <p className="font-bold text-slate-800">{formatCurrency(r.dailyRate)}/day</p>
                    </div>
                    <div>
                      <p className="text-slate-400 font-medium">Start Date</p>
                      <p className="font-mono text-slate-600">{r.startDate}</p>
                    </div>
                    <div>
                      <p className="text-slate-400 font-medium">Return Expected</p>
                      <p className="font-mono text-slate-600">{r.expectedReturnDate}</p>
                    </div>
                  </div>

                  <div className="pt-2 flex items-center justify-between">
                    <span className="text-[11px] text-slate-500 font-medium">Operator: {r.operatorName || 'Unassigned'}</span>
                    <button
                      onClick={() => setCheckInRental(r)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-bold text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 transition-colors shadow-2xs"
                    >
                      <ArrowDownLeft className="w-3.5 h-3.5" /> Check-In
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Tab 2: Recent Rental Activities */}
        {rentalTab === 'activities' && (
          <div className="space-y-3 pt-2">
            {INITIAL_ACTIVITIES.filter((a) => a.type === 'rental' || a.type === 'equipment').concat([
              {
                id: 'ACT-005',
                title: 'Dealer Dispatch Dispatched',
                description: 'Cat 320 Hydraulic Excavator check-out confirmed with Empire Cat Dealer for Apex Mine Site A.',
                timestamp: '4 hours ago',
                type: 'rental',
              },
              {
                id: 'ACT-006',
                title: 'Contract Extended',
                description: 'Cat 745 Articulated Dump Truck rental contract extension requested with dealer network.',
                timestamp: '5 hours ago',
                type: 'rental',
              },
            ]).map((act) => (
              <div key={act.id} className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex items-start gap-3">
                <div className="p-2 rounded-lg bg-blue-50 text-blue-600 mt-0.5">
                  <KeyRound className="w-4 h-4" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-bold text-slate-800">{act.title}</p>
                    <span className="text-[10px] text-slate-400 font-medium">{act.timestamp}</span>
                  </div>
                  <p className="text-xs text-slate-600 mt-0.5">{act.description}</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Tab 3: Rental History Preview */}
        {rentalTab === 'history' && (
          <div className="overflow-x-auto rounded-xl border border-slate-100">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-400 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                <tr>
                  <th className="px-4 py-3 font-bold">Rental ID</th>
                  <th className="px-4 py-3 font-bold">Equipment & Dealer</th>
                  <th className="px-4 py-3 font-bold">Site</th>
                  <th className="px-4 py-3 font-bold">Start Date</th>
                  <th className="px-4 py-3 font-bold">Expected Return</th>
                  <th className="px-4 py-3 font-bold">Daily Rate</th>
                  <th className="px-4 py-3 font-bold">Total Cost</th>
                  <th className="px-4 py-3 font-bold">Status</th>
                  <th className="px-4 py-3 font-bold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredRentals.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="p-8 text-center text-slate-400 font-medium">
                      No rental records match the search filter.
                    </td>
                  </tr>
                ) : (
                  filteredRentals.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-50/60 transition-colors text-slate-600">
                      <td className="px-4 py-3 font-mono font-bold text-blue-600">{r.id}</td>
                      <td className="px-4 py-3">
                        <div className="font-bold text-slate-800">{r.equipmentName}</div>
                        <div className="text-[10px] text-slate-400">{r.dealerName}</div>
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-700">{r.siteName}</td>
                      <td className="px-4 py-3 font-mono text-slate-600">{r.startDate}</td>
                      <td className="px-4 py-3 font-mono text-slate-600">
                        {r.actualReturnDate ? (
                          <span className="text-emerald-700 font-semibold block text-[10px]">
                            Returned: {r.actualReturnDate}
                          </span>
                        ) : (
                          r.expectedReturnDate
                        )}
                      </td>
                      <td className="px-4 py-3 font-bold text-slate-800">{formatCurrency(r.dailyRate)}</td>
                      <td className="px-4 py-3 font-bold text-blue-600">{formatCurrency(r.totalCost)}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        {r.status !== 'Returned' ? (
                          <button
                            onClick={() => setCheckInRental(r)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-white bg-emerald-600 rounded-md hover:bg-emerald-700 transition-colors"
                          >
                            <ArrowDownLeft className="w-3.5 h-3.5" /> Check-In
                          </button>
                        ) : (
                          <span className="text-[11px] text-slate-400 font-medium italic">Completed</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 5. Alerts Preview */}
      <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-red-500" />
            <div>
              <h2 className="text-base font-bold text-slate-800">System Alerts Preview</h2>
              <p className="text-xs text-slate-500 mt-0.5">Critical notifications requiring equipment manager review</p>
            </div>
          </div>
          <Link
            to="/alerts"
            className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
          >
            View All Alerts <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {alerts.slice(0, 3).map((alt) => (
            <div
              key={alt.id}
              className={`p-4 rounded-xl border flex flex-col justify-between ${
                alt.severity === 'Danger'
                  ? 'bg-red-50/50 border-red-100'
                  : 'bg-amber-50/50 border-amber-100'
              }`}
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 font-mono">
                    {alt.id}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                      alt.severity === 'Danger'
                        ? 'bg-red-100 text-red-700'
                        : 'bg-amber-100 text-amber-700'
                    }`}
                  >
                    {alt.type}
                  </span>
                </div>
                <h3 className="font-bold text-slate-800 text-xs mt-2">{alt.title}</h3>
                <p className="text-[11px] text-slate-600 mt-1 line-clamp-2">{alt.message}</p>
              </div>

              <div className="mt-3 pt-2 border-t border-slate-200/50 flex items-center justify-between text-[10px]">
                <span className="text-slate-400 font-medium">{alt.timestamp}</span>
                <span className="font-bold text-blue-600 hover:underline cursor-pointer">{alt.actionRequired}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Check-Out Modal */}
      <Modal isOpen={isCheckOutOpen} onClose={() => setIsCheckOutOpen(false)} title="Equipment Check-Out Contract">
        <form onSubmit={handleCheckOutSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Equipment Unit</label>
              <select
                value={checkOutForm.equipmentId}
                onChange={(e) => handleEquipmentSelect(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-slate-900 bg-white"
              >
                {equipmentList.map((eq) => (
                  <option key={eq.id} value={eq.id}>
                    {eq.name} ({eq.id})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Caterpillar Dealer Partner</label>
              <input
                type="text"
                required
                value={checkOutForm.dealerName}
                onChange={(e) => setCheckOutForm({ ...checkOutForm, dealerName: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Rental Start Date</label>
              <input
                type="date"
                required
                value={checkOutForm.startDate}
                onChange={(e) => setCheckOutForm({ ...checkOutForm, startDate: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Expected Return Date</label>
              <input
                type="date"
                required
                value={checkOutForm.expectedReturnDate}
                onChange={(e) => setCheckOutForm({ ...checkOutForm, expectedReturnDate: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Agreed Daily Rate ($/day)</label>
              <input
                type="number"
                required
                min={50}
                value={checkOutForm.dailyRate}
                onChange={(e) => setCheckOutForm({ ...checkOutForm, dailyRate: Number(e.target.value) })}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Dispatch Site Location</label>
              <input
                type="text"
                required
                value={checkOutForm.siteName}
                onChange={(e) => setCheckOutForm({ ...checkOutForm, siteName: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-slate-900"
              />
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={() => setIsCheckOutOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 rounded-xl hover:bg-blue-700"
            >
              Confirm Check-Out
            </button>
          </div>
        </form>
      </Modal>

      {/* Check-In Modal */}
      {checkInRental && (
        <Modal
          isOpen={checkInRental !== null}
          onClose={() => setCheckInRental(null)}
          title={`Check-In Rental Return: ${checkInRental.id}`}
        >
          <form onSubmit={handleCheckInSubmit} className="space-y-4">
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl">
              <p className="text-sm font-bold text-slate-900">{checkInRental.equipmentName}</p>
              <p className="text-xs text-slate-500 mt-1">
                Dealer: {checkInRental.dealerName} • Site: {checkInRental.siteName}
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Actual Return Date</label>
              <input
                type="date"
                required
                value={checkInDate}
                onChange={(e) => setCheckInDate(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 text-slate-900"
              />
            </div>

            <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setCheckInRental(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 text-xs font-semibold text-white bg-emerald-600 rounded-xl hover:bg-emerald-700"
              >
                Complete Check-In
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Toast Notification */}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
};
