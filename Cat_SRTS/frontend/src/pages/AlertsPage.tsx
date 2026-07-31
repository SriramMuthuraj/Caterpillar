import React, { useState, useEffect } from 'react';
import {
  Bell,
  AlertTriangle,
  Clock,
  Wrench,
  Gauge,
  CheckCircle2,
  XCircle,
  Filter,
  Check,
  Trash2,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { SearchInput } from '../components/ui/SearchInput';
import { Toast, ToastMessage } from '../components/ui/Toast';
import { alertService } from '../services/alertService';
import { SystemAlert, AlertSeverity, AlertType } from '../types';

export const AlertsPage: React.FC = () => {
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [severityFilter, setSeverityFilter] = useState<string>('All');
  const [typeFilter, setTypeFilter] = useState<string>('All');

  const [toast, setToast] = useState<ToastMessage | null>(null);

  const loadAlerts = async () => {
    setLoading(true);
    const data = await alertService.getAll();
    setAlerts(data);
    setLoading(false);
  };

  useEffect(() => {
    loadAlerts();
  }, []);

  const handleMarkRead = async (id: string) => {
    await alertService.markAsRead(id);
    setToast({
      id: Date.now().toString(),
      type: 'info',
      title: 'Alert Acknowledged',
      message: `Alert ${id} has been marked as read.`,
    });
    loadAlerts();
  };

  const handleDismiss = async (id: string) => {
    await alertService.dismiss(id);
    setToast({
      id: Date.now().toString(),
      type: 'info',
      title: 'Alert Dismissed',
      message: `Alert ${id} removed from feed.`,
    });
    loadAlerts();
  };

  const filteredAlerts = alerts.filter((a) => {
    const q = search.toLowerCase();
    const matchesSearch =
      a.title.toLowerCase().includes(q) ||
      a.equipmentName.toLowerCase().includes(q) ||
      a.message.toLowerCase().includes(q);
    const matchesSeverity = severityFilter === 'All' || a.severity === severityFilter;
    const matchesType = typeFilter === 'All' || a.type === typeFilter;
    return matchesSearch && matchesSeverity && matchesType;
  });

  const getSeverityStyle = (severity: AlertSeverity) => {
    switch (severity) {
      case 'Danger':
        return {
          cardBg: 'bg-red-50/60 border-red-200',
          badgeBg: 'bg-red-100 text-red-800 border-red-200',
          iconColor: 'text-red-600',
          btnBg: 'bg-red-600 hover:bg-red-700 text-white',
        };
      case 'Warning':
        return {
          cardBg: 'bg-amber-50/60 border-amber-200',
          badgeBg: 'bg-amber-100 text-amber-800 border-amber-200',
          iconColor: 'text-amber-600',
          btnBg: 'bg-amber-600 hover:bg-amber-700 text-white',
        };
      case 'Info':
      default:
        return {
          cardBg: 'bg-blue-50/60 border-blue-200',
          badgeBg: 'bg-blue-100 text-blue-800 border-blue-200',
          iconColor: 'text-blue-600',
          btnBg: 'bg-blue-600 hover:bg-blue-700 text-white',
        };
    }
  };

  const getTypeIcon = (type: AlertType) => {
    switch (type) {
      case 'Overdue':
        return <AlertTriangle className="w-5 h-5 text-red-600" />;
      case 'Return Due':
        return <Clock className="w-5 h-5 text-amber-600" />;
      case 'Maintenance Reminder':
        return <Wrench className="w-5 h-5 text-amber-600" />;
      case 'Idle Equipment':
      default:
        return <Gauge className="w-5 h-5 text-blue-600" />;
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fleet Alerts & Telematics Warnings"
        description="Real-time automated warnings for overdue rentals, impending return deadlines, maintenance schedules, and excessive idle engine hours."
        action={
          <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 bg-red-50 text-red-700 border border-red-200 rounded-lg">
            Unread Alerts: {alerts.filter((a) => !a.isRead).length}
          </div>
        }
      />

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="w-full md:w-80">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search alert title, equipment or message..."
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 font-medium">
            <Filter className="w-3.5 h-3.5" /> Filters:
          </div>

          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-800"
          >
            <option value="All">All Categories</option>
            <option value="Overdue">Overdue</option>
            <option value="Return Due">Return Due</option>
            <option value="Maintenance Reminder">Maintenance Reminder</option>
            <option value="Idle Equipment">Idle Equipment</option>
          </select>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-800"
          >
            <option value="All">All Severities</option>
            <option value="Danger">Danger (Critical)</option>
            <option value="Warning">Warning</option>
            <option value="Info">Info</option>
          </select>
        </div>
      </div>

      {/* Alert Cards Feed */}
      <div className="space-y-4">
        {loading ? (
          <div className="p-8 text-center text-gray-500 bg-white rounded-xl border border-gray-200">
            Loading telematics alert notifications...
          </div>
        ) : filteredAlerts.length === 0 ? (
          <div className="p-12 text-center text-gray-500 bg-white rounded-xl border border-gray-200">
            <Bell className="w-8 h-8 text-gray-300 mx-auto mb-2" />
            No active system alerts match your current filter criteria.
          </div>
        ) : (
          filteredAlerts.map((alert) => {
            const styles = getSeverityStyle(alert.severity);
            return (
              <div
                key={alert.id}
                className={`p-5 rounded-xl border transition-all shadow-xs ${styles.cardBg} ${
                  !alert.isRead ? 'ring-1 ring-blue-400' : 'opacity-90'
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  <div className="flex items-start gap-3.5">
                    <div className="p-2.5 rounded-lg bg-white shadow-xs border border-gray-200 flex-shrink-0">
                      {getTypeIcon(alert.type)}
                    </div>

                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-bold text-gray-900">{alert.title}</h3>
                        <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full border ${styles.badgeBg}`}>
                          {alert.type}
                        </span>
                        <span className="text-[11px] text-gray-500 font-mono">• {alert.equipmentName}</span>
                      </div>

                      <p className="text-xs text-gray-700 mt-1.5 leading-relaxed">{alert.message}</p>

                      <div className="mt-2 flex items-center gap-4 text-[11px] text-gray-500">
                        <span>Timestamp: {alert.timestamp}</span>
                        <span>Equipment ID: {alert.equipmentId}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 sm:flex-col sm:items-end flex-shrink-0">
                    {alert.actionRequired && (
                      <span className="text-[11px] font-semibold text-gray-900 bg-white px-2.5 py-1 rounded-md border border-gray-200 shadow-2xs">
                        Action: {alert.actionRequired}
                      </span>
                    )}

                    <div className="flex items-center gap-1.5 mt-1">
                      {!alert.isRead && (
                        <button
                          onClick={() => handleMarkRead(alert.id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-gray-700 bg-white hover:bg-gray-50 border border-gray-300 rounded-lg transition-colors"
                        >
                          <Check className="w-3.5 h-3.5 text-blue-600" /> Acknowledge
                        </button>
                      )}
                      <button
                        onClick={() => handleDismiss(alert.id)}
                        className="p-1 text-gray-400 hover:text-red-600 rounded-lg hover:bg-white transition-colors"
                        title="Dismiss Alert"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
};
