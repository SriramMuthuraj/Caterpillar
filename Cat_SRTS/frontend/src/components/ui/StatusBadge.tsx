import React from 'react';
import { getStatusBadgeStyle } from '../../utils/formatters';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'sm' }) => {
  const { bg, dot } = getStatusBadgeStyle(status);

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium border rounded-full ${
        size === 'sm' ? 'px-2.5 py-0.5 text-xs' : 'px-3 py-1 text-sm'
      } ${bg}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      <span className="whitespace-nowrap">{status}</span>
    </span>
  );
};
