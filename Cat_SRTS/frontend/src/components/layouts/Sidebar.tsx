import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  ClipboardEdit,
  Truck,
  UserCheck,
  Link2,
  Boxes,
  Gauge,
  Bell,
  User,
  ChevronDown,
  ChevronRight,
  TrendingUp,
  ShieldAlert,
} from 'lucide-react';

interface SidebarProps {
  isOpen: boolean;
  onCloseMobile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onCloseMobile }) => {
  const location = useLocation();
  const isRegistrationPath = location.pathname.startsWith('/registration');
  const [isRegistrationOpen, setIsRegistrationOpen] = useState(isRegistrationPath);

  const mainNavItemClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 px-3 py-2 text-xs font-medium rounded-lg transition-colors ${
      isActive
        ? 'bg-blue-50 text-blue-700 font-semibold'
        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
    }`;

  const subNavItemClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2.5 px-3 py-1.5 pl-8 text-xs font-medium rounded-lg transition-colors ${
      isActive
        ? 'bg-blue-50 text-blue-700 font-semibold'
        : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
    }`;

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 z-40 bg-gray-900/40 backdrop-blur-xs lg:hidden"
        />
      )}

      <aside
        className={`fixed top-16 bottom-0 left-0 z-40 w-64 bg-white border-r border-gray-200 flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1.5">
          <div className="px-3 pb-2 text-[10px] font-bold tracking-wider text-gray-400 uppercase">
            Main Navigation
          </div>

          {/* Dashboard */}
          <NavLink to="/dashboard" onClick={onCloseMobile} className={mainNavItemClass}>
            <LayoutDashboard className="w-4 h-4 flex-shrink-0" />
            <span>Dashboard</span>
          </NavLink>

          {/* Registration Submenu */}
          <div>
            <button
              onClick={() => setIsRegistrationOpen(!isRegistrationOpen)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 text-xs font-semibold rounded-lg transition-colors ${
                isRegistrationPath
                  ? 'text-blue-700 font-bold bg-blue-50/50'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100/80'
              }`}
            >
              <div className="flex items-center gap-3">
                <ClipboardEdit className="w-4 h-4 flex-shrink-0 text-gray-500" />
                <span>Registration</span>
              </div>
              {isRegistrationOpen ? (
                <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
              )}
            </button>

            {isRegistrationOpen && (
              <div className="mt-1 space-y-1 pl-1 border-l-2 border-gray-100 ml-4">
                <NavLink
                  to="/registration/equipment"
                  onClick={onCloseMobile}
                  className={subNavItemClass}
                >
                  <Truck className="w-3.5 h-3.5 flex-shrink-0" />
                  <span>Equipment Registration</span>
                </NavLink>

                <NavLink
                  to="/registration/operators"
                  onClick={onCloseMobile}
                  className={subNavItemClass}
                >
                  <UserCheck className="w-3.5 h-3.5 flex-shrink-0" />
                  <span>Operator Registration</span>
                </NavLink>

                <NavLink
                  to="/registration/assignment"
                  onClick={onCloseMobile}
                  className={subNavItemClass}
                >
                  <Link2 className="w-3.5 h-3.5 flex-shrink-0" />
                  <span>Equipment Assignment</span>
                </NavLink>
              </div>
            )}
          </div>

          {/* Asset Management */}
          <NavLink to="/assets" onClick={onCloseMobile} className={mainNavItemClass}>
            <Boxes className="w-4 h-4 flex-shrink-0" />
            <span>Asset Management</span>
          </NavLink>

          {/* Usage Logging */}
          <NavLink to="/usage" onClick={onCloseMobile} className={mainNavItemClass}>
            <Gauge className="w-4 h-4 flex-shrink-0" />
            <span>Usage Logging</span>
          </NavLink>

          {/* Alerts */}
          <NavLink to="/alerts" onClick={onCloseMobile} className={mainNavItemClass}>
            <Bell className="w-4 h-4 flex-shrink-0" />
            <div className="flex-1 flex items-center justify-between">
              <span>Alerts</span>
              <span className="px-1.5 py-0.5 text-[10px] font-bold bg-red-100 text-red-700 rounded-full">
                4
              </span>
            </div>
          </NavLink>

          {/* The two predictive modules. Kept in their own group because they
              answer questions rather than record facts, unlike everything above. */}
          <div className="pt-4 pb-1">
            <div className="px-3 pb-2 text-[10px] font-bold tracking-wider text-gray-400 uppercase">
              Intelligence
            </div>

            <NavLink to="/forecast" onClick={onCloseMobile} className={mainNavItemClass}>
              <TrendingUp className="w-4 h-4 flex-shrink-0" />
              <span>Demand Forecast</span>
            </NavLink>

            <NavLink to="/anomalies" onClick={onCloseMobile} className={mainNavItemClass}>
              <ShieldAlert className="w-4 h-4 flex-shrink-0" />
              <span>Anomaly Detection</span>
            </NavLink>
          </div>

          <div className="pt-4 pb-1">
            <div className="px-3 pb-2 text-[10px] font-bold tracking-wider text-gray-400 uppercase">
              Account
            </div>

            {/* Profile */}
            <NavLink to="/profile" onClick={onCloseMobile} className={mainNavItemClass}>
              <User className="w-4 h-4 flex-shrink-0" />
              <span>Profile & Settings</span>
            </NavLink>
          </div>
        </div>

        {/* Sleek User Profile Footer */}
        <div className="p-3 border-t border-slate-100">
          <NavLink
            to="/profile"
            onClick={onCloseMobile}
            className="flex items-center gap-3 p-2 bg-slate-50 hover:bg-slate-100/80 rounded-xl transition-colors border border-slate-100 group"
          >
            <div className="w-8 h-8 rounded-full bg-blue-600 text-white font-bold text-xs flex items-center justify-center flex-shrink-0 shadow-xs">
              AM
            </div>
            <div className="overflow-hidden">
              <p className="text-xs font-semibold text-slate-800 truncate group-hover:text-blue-600 transition-colors">
                Alex Mercer
              </p>
              <p className="text-[10px] text-slate-500 truncate">Equipment Manager</p>
            </div>
          </NavLink>
        </div>
      </aside>
    </>
  );
};
