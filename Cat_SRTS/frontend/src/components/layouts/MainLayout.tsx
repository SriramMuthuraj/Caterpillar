import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { Breadcrumb } from './Breadcrumb';

export const MainLayout: React.FC = () => {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-gray-900 flex flex-col font-sans">
      <Navbar
        onToggleSidebar={() => setIsMobileSidebarOpen(!isMobileSidebarOpen)}
        isSidebarOpen={isMobileSidebarOpen}
      />

      <div className="flex flex-1">
        <Sidebar
          isOpen={isMobileSidebarOpen}
          onCloseMobile={() => setIsMobileSidebarOpen(false)}
        />

        {/* Main Content Area */}
        <main className="flex-1 lg:pl-64 flex flex-col min-w-0 transition-all">
          <div className="p-4 sm:p-6 lg:p-8 flex-1 max-w-7xl w-full mx-auto">
            <Breadcrumb />
            <Outlet />
          </div>

          <footer className="border-t border-slate-200 bg-white py-4 px-6 text-center text-xs text-slate-500">
            <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 font-medium">
              <p>© {new Date().getFullYear()} STRATOS ERP • Enterprise Rental & Telematics Platform</p>
              <p className="text-slate-400">Connected Dealer: Empire Cat Equipment • Version 2.4.0</p>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
};
