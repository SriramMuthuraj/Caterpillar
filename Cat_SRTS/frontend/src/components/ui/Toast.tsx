import React, { useEffect } from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info';
  title: string;
  message?: string;
}

interface ToastProps {
  toast: ToastMessage | null;
  onClose: () => void;
}

export const Toast: React.FC<ToastProps> = ({ toast, onClose }) => {
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => {
        onClose();
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [toast, onClose]);

  if (!toast) return null;

  const icons = {
    success: <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />,
    error: <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />,
    info: <Info className="w-5 h-5 text-blue-600 flex-shrink-0" />,
  };

  const borders = {
    success: 'border-emerald-200 bg-emerald-50/90',
    error: 'border-red-200 bg-red-50/90',
    info: 'border-blue-200 bg-blue-50/90',
  };

  return (
    <div className="fixed bottom-5 right-5 z-50 max-w-sm w-full animate-in slide-in-from-bottom-5 duration-200">
      <div className={`p-4 rounded-xl border shadow-lg flex items-start gap-3 backdrop-blur-sm ${borders[toast.type]}`}>
        {icons[toast.type]}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-900">{toast.title}</p>
          {toast.message && <p className="text-xs text-gray-600 mt-0.5">{toast.message}</p>}
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 p-0.5">
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
