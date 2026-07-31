import React from 'react';
import { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtext?: string;
  icon?: LucideIcon;
  badge?: {
    text: string;
    variant: 'success' | 'warning' | 'danger' | 'info';
  };
}

export const MetricCard: React.FC<MetricCardProps> = ({ title, value, subtext, icon: Icon, badge }) => {
  const badgeClasses = {
    success: 'bg-emerald-50 text-emerald-700 border-emerald-100',
    warning: 'bg-amber-50 text-amber-700 border-amber-100',
    danger: 'bg-red-50 text-red-700 border-red-100',
    info: 'bg-blue-50 text-blue-700 border-blue-100',
  };

  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 flex flex-col justify-between hover:border-slate-200 transition-all">
      <div>
        <div className="flex items-center justify-between">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">{title}</p>
          {Icon && (
            <div className="p-2 rounded-xl bg-blue-50 text-blue-600">
              <Icon className="w-4 h-4" />
            </div>
          )}
        </div>
        <h3 className="text-2xl sm:text-3xl font-bold text-slate-800 mt-1">{value}</h3>
      </div>

      <div className="mt-3 flex items-center justify-between">
        {subtext && <p className="text-xs text-slate-500 font-medium">{subtext}</p>}
        {badge && (
          <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md border ${badgeClasses[badge.variant]}`}>
            {badge.text}
          </span>
        )}
      </div>
    </div>
  );
};
