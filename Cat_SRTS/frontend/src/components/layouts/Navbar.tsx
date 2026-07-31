import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Bell,
  Search,
  User,
  Sun,
  Menu,
  X,
  Building2,
  AlertTriangle,
  ChevronDown,
  LogOut,
  Settings,
} from 'lucide-react';
import { alertService } from '../../services/alertService';
import { SystemAlert } from '../../types';

interface NavbarProps {
  onToggleSidebar: () => void;
  isSidebarOpen: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({ onToggleSidebar }) => {
  const navigate = useNavigate();
  const [globalSearch, setGlobalSearch] = useState('');
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);

  useEffect(() => {
    alertService.getAll().then(setAlerts);
  }, []);

  const unreadAlerts = alerts.filter((a) => !a.isRead);

  const handleGlobalSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (globalSearch.trim()) {
      navigate(`/assets?q=${encodeURIComponent(globalSearch.trim())}`);
      setGlobalSearch('');
    }
  };

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-slate-200 h-16 flex items-center justify-between px-4 sm:px-8">
      {/* Left: Mobile menu toggle + Branding */}
      <div className="flex items-center gap-3 lg:gap-4">
        <button
          onClick={onToggleSidebar}
          className="p-2 text-slate-600 rounded-lg lg:hidden hover:bg-slate-50 focus:outline-hidden"
          aria-label="Toggle menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <Link to="/dashboard" className="flex items-center gap-3 group">
          <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center text-white font-bold text-lg shadow-xs group-hover:scale-105 transition-transform flex-shrink-0">
            S
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-slate-800 text-base sm:text-lg tracking-tight group-hover:text-blue-600 transition-colors">
                STRATOS ERP
              </span>
              <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-blue-50 text-blue-700">
                Rental Portal
              </span>
            </div>
            <p className="hidden md:block text-[11px] text-slate-500 font-medium">
              Apex Infrastructure & Mining Services
            </p>
          </div>
        </Link>
      </div>

      {/* Middle: Global Search */}
      <div className="hidden md:flex items-center justify-center flex-1 max-w-md mx-6">
        <form onSubmit={handleGlobalSearchSubmit} className="w-full relative max-w-xs">
          <input
            type="text"
            value={globalSearch}
            onChange={(e) => setGlobalSearch(e.target.value)}
            placeholder="Search records..."
            className="w-full bg-slate-100 border-none rounded-full px-4 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:ring-2 focus:ring-blue-400 outline-none transition-all"
          />
        </form>
      </div>

      {/* Right: Notifications, Theme, Profile */}
      <div className="flex items-center gap-1.5 sm:gap-3">
        {/* Theme indicator */}
        <div
          title="Theme: Enterprise Light Theme"
          className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-gray-600 bg-gray-50 border border-gray-200 rounded-lg cursor-default"
        >
          <Sun className="w-3.5 h-3.5 text-amber-500" />
          <span className="text-[11px]">Light Mode</span>
        </div>

        {/* Notifications Dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              setIsNotificationsOpen(!isNotificationsOpen);
              setIsProfileMenuOpen(false);
            }}
            className="relative p-2 text-gray-600 hover:text-blue-600 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label="Notifications"
          >
            <Bell className="w-5 h-5" />
            {unreadAlerts.length > 0 && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-red-500 ring-2 ring-white animate-pulse" />
            )}
          </button>

          {isNotificationsOpen && (
            <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-white rounded-xl shadow-xl border border-gray-200 py-2 z-50 animate-in fade-in duration-150">
              <div className="px-4 py-2 border-b border-gray-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm text-gray-900">System Notifications</span>
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-700">
                    {unreadAlerts.length} New
                  </span>
                </div>
                <button
                  onClick={() => setIsNotificationsOpen(false)}
                  className="text-gray-400 hover:text-gray-600 p-1"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="max-h-80 overflow-y-auto divide-y divide-gray-50">
                {alerts.length === 0 ? (
                  <p className="p-4 text-xs text-center text-gray-500">No active notifications</p>
                ) : (
                  alerts.slice(0, 4).map((alert) => (
                    <div
                      key={alert.id}
                      className={`p-3.5 hover:bg-gray-50 transition-colors ${
                        !alert.isRead ? 'bg-blue-50/40' : ''
                      }`}
                    >
                      <div className="flex items-start gap-2.5">
                        <AlertTriangle
                          className={`w-4 h-4 flex-shrink-0 mt-0.5 ${
                            alert.severity === 'Danger'
                              ? 'text-red-500'
                              : alert.severity === 'Warning'
                              ? 'text-amber-500'
                              : 'text-blue-500'
                          }`}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <p className="text-xs font-semibold text-gray-900 truncate">{alert.title}</p>
                            <span className="text-[10px] text-gray-400">{alert.timestamp.split(' ')[0]}</span>
                          </div>
                          <p className="text-xs text-gray-600 mt-1 line-clamp-2">{alert.message}</p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="p-2 border-t border-gray-100 bg-gray-50 text-center">
                <Link
                  to="/alerts"
                  onClick={() => setIsNotificationsOpen(false)}
                  className="text-xs font-semibold text-blue-600 hover:text-blue-700 inline-block w-full py-1"
                >
                  View All Alerts ({alerts.length})
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* Profile Menu Dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              setIsProfileMenuOpen(!isProfileMenuOpen);
              setIsNotificationsOpen(false);
            }}
            className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-100 transition-colors focus:outline-hidden"
          >
            <div className="w-8 h-8 rounded-full bg-blue-600 text-white font-semibold text-xs flex items-center justify-center shadow-xs">
              AM
            </div>
            <div className="hidden lg:block text-left">
              <p className="text-xs font-semibold text-gray-900 leading-none">Alex Mercer</p>
              <p className="text-[10px] text-gray-500 font-medium leading-none mt-1">Equipment Mgr</p>
            </div>
            <ChevronDown className="hidden lg:block w-3.5 h-3.5 text-gray-400" />
          </button>

          {isProfileMenuOpen && (
            <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-xl border border-gray-200 py-1 z-50 animate-in fade-in duration-150">
              <div className="px-4 py-3 border-b border-gray-100">
                <p className="text-xs font-semibold text-gray-900">Alex Mercer</p>
                <p className="text-[11px] text-gray-500 truncate">a.mercer@apexinfrastructure.com</p>
                <div className="mt-2 flex items-center gap-1.5 text-[10px] font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded-md border border-blue-100">
                  <Building2 className="w-3 h-3 text-blue-600" />
                  <span>Apex Infrastructure LLC</span>
                </div>
              </div>

              <Link
                to="/profile"
                onClick={() => setIsProfileMenuOpen(false)}
                className="flex items-center gap-2 px-4 py-2 text-xs text-gray-700 hover:bg-gray-50 transition-colors"
              >
                <User className="w-4 h-4 text-gray-400" />
                Customer Profile
              </Link>
              <Link
                to="/profile"
                onClick={() => setIsProfileMenuOpen(false)}
                className="flex items-center gap-2 px-4 py-2 text-xs text-gray-700 hover:bg-gray-50 transition-colors"
              >
                <Settings className="w-4 h-4 text-gray-400" />
                Company Settings
              </Link>

              <div className="border-t border-gray-100 my-1" />

              <Link
                to="/profile"
                onClick={() => setIsProfileMenuOpen(false)}
                className="flex items-center gap-2 px-4 py-2 text-xs text-red-600 hover:bg-red-50 transition-colors"
              >
                <LogOut className="w-4 h-4 text-red-500" />
                Sign Out
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
