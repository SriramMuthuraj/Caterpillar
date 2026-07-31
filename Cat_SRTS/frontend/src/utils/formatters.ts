export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatNumber(val: number): string {
  return new Intl.NumberFormat('en-US').format(val);
}

export function getStatusBadgeStyle(status: string): { bg: string; text: string; dot: string } {
  switch (status.toLowerCase()) {
    case 'active':
    case 'working':
    case 'assigned':
      return {
        bg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        text: 'text-emerald-700',
        dot: 'bg-emerald-500',
      };
    case 'idle':
    case 'warning':
    case 'pending return':
    case 'unassigned':
      return {
        bg: 'bg-amber-50 text-amber-700 border-amber-200',
        text: 'text-amber-700',
        dot: 'bg-amber-500',
      };
    case 'overdue':
    case 'danger':
    case 'maintenance':
    case 'inactive':
      return {
        bg: 'bg-red-50 text-red-700 border-red-200',
        text: 'text-red-700',
        dot: 'bg-red-500',
      };
    case 'returned':
    case 'completed':
    case 'info':
    default:
      return {
        bg: 'bg-blue-50 text-blue-700 border-blue-200',
        text: 'text-blue-700',
        dot: 'bg-blue-500',
      };
  }
}
