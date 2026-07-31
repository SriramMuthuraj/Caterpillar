import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';

const routeLabels: Record<string, string> = {
  dashboard: 'Dashboard',
  registration: 'Registration',
  equipment: 'Equipment Registration',
  operators: 'Operator Registration',
  assignment: 'Equipment Assignment',
  assets: 'Asset Management',
  usage: 'Usage Logging',
  alerts: 'Alerts',
  profile: 'Profile & Settings',
};

export const Breadcrumb: React.FC = () => {
  const location = useLocation();
  const pathnames = location.pathname.split('/').filter((x) => x);

  return (
    <nav className="flex items-center text-xs text-gray-500 mb-4" aria-label="Breadcrumb">
      <ol className="inline-flex items-center space-x-1 md:space-x-2">
        <li className="inline-flex items-center">
          <Link to="/dashboard" className="inline-flex items-center text-gray-500 hover:text-blue-600 font-medium transition-colors">
            <Home className="w-3.5 h-3.5 mr-1.5" />
            Home
          </Link>
        </li>
        {pathnames.map((value, index) => {
          const to = `/${pathnames.slice(0, index + 1).join('/')}`;
          const isLast = index === pathnames.length - 1;
          const label = routeLabels[value] || value.charAt(0).toUpperCase() + value.slice(1);

          return (
            <li key={to} className="inline-flex items-center">
              <ChevronRight className="w-3.5 h-3.5 text-gray-400 mx-1" />
              {isLast ? (
                <span className="font-semibold text-gray-900">{label}</span>
              ) : (
                <Link to={to} className="text-gray-500 hover:text-blue-600 font-medium transition-colors">
                  {label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};
