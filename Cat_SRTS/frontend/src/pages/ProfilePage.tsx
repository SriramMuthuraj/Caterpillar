import React, { useState, useEffect } from 'react';
import {
  User,
  Building2,
  Settings,
  LogOut,
  Save,
  Shield,
  BellRing,
  MapPin,
  Globe,
  FileText,
  Building,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { Toast, ToastMessage } from '../components/ui/Toast';
import { profileService } from '../services/profileService';
import { CustomerProfile } from '../types';

export const ProfilePage: React.FC = () => {
  const [profile, setProfile] = useState<CustomerProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastMessage | null>(null);

  // Logout confirm modal state
  const [isLogoutOpen, setIsLogoutOpen] = useState(false);

  const loadProfile = async () => {
    setLoading(true);
    const p = await profileService.getProfile();
    setProfile(p);
    setLoading(false);
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;

    await profileService.updateProfile(profile);
    setToast({
      id: Date.now().toString(),
      type: 'success',
      title: 'Profile Updated',
      message: 'Your customer information and company preferences have been saved.',
    });
  };

  const handleConfirmLogout = () => {
    setToast({
      id: Date.now().toString(),
      type: 'info',
      title: 'Signed Out',
      message: 'You have been logged out of Smart Rental Tracking System.',
    });
  };

  if (loading || !profile) {
    return (
      <div className="p-8 text-center text-gray-500 bg-white rounded-xl border border-gray-200">
        Loading customer account profile...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Customer Profile & Company Settings"
        description="Manage your enterprise account details, Caterpillar dealer billing address, notification preferences, and default dispatch site."
        action={
          <button
            onClick={() => setIsLogoutOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg transition-colors"
          >
            <LogOut className="w-4 h-4" /> Sign Out
          </button>
        }
      />

      <form onSubmit={handleSaveProfile} className="space-y-6">
        {/* Customer Information Card */}
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-xs space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-gray-100">
            <User className="w-5 h-5 text-blue-600" />
            <h2 className="text-base font-bold text-gray-900">Customer Account Information</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Customer Account ID</label>
              <input
                type="text"
                disabled
                value={profile.id}
                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg font-mono text-gray-500 cursor-not-allowed"
              />
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">Full Name</label>
              <input
                type="text"
                required
                value={profile.name}
                onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">Role / Job Title</label>
              <input
                type="text"
                required
                value={profile.role}
                onChange={(e) => setProfile({ ...profile, role: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">Email Address</label>
              <input
                type="email"
                required
                value={profile.email}
                onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">Phone Number</label>
              <input
                type="text"
                required
                value={profile.phone}
                onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>
          </div>
        </div>

        {/* Company Details Card */}
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-xs space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-gray-100">
            <Building2 className="w-5 h-5 text-blue-600" />
            <h2 className="text-base font-bold text-gray-900">Company & Caterpillar Partner Details</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Company Legal Name</label>
              <input
                type="text"
                required
                value={profile.companyName}
                onChange={(e) => setProfile({ ...profile, companyName: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">Federal Tax ID / EIN</label>
              <input
                type="text"
                required
                value={profile.taxId}
                onChange={(e) => setProfile({ ...profile, taxId: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-gray-900"
              />
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">CAT Dealer Account No.</label>
              <input
                type="text"
                disabled
                value={profile.accountNumber}
                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg font-mono text-gray-500 cursor-not-allowed"
              />
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">Primary Caterpillar Dealer</label>
              <input
                type="text"
                required
                value={profile.primaryDealer}
                onChange={(e) => setProfile({ ...profile, primaryDealer: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div className="sm:col-span-2">
              <label className="block font-semibold text-gray-700 mb-1">Billing & Contract Address</label>
              <input
                type="text"
                required
                value={profile.billingAddress}
                onChange={(e) => setProfile({ ...profile, billingAddress: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>
          </div>
        </div>

        {/* Regional & Notification Settings Card */}
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-xs space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-gray-100">
            <Settings className="w-5 h-5 text-blue-600" />
            <h2 className="text-base font-bold text-gray-900">Application Preferences & Notifications</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-gray-700 mb-1">Default Site Location</label>
              <input
                type="text"
                required
                value={profile.defaultSite}
                onChange={(e) => setProfile({ ...profile, defaultSite: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">System Timezone</label>
              <input
                type="text"
                required
                value={profile.timezone}
                onChange={(e) => setProfile({ ...profile, timezone: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block font-semibold text-gray-700 mb-1">Display Language</label>
              <input
                type="text"
                required
                value={profile.language}
                onChange={(e) => setProfile({ ...profile, language: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>
          </div>

          <div className="pt-2 border-t border-gray-100">
            <span className="block font-semibold text-xs text-gray-800 mb-3">Notification Alert Triggers</span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={profile.notificationPreferences.emailAlerts}
                  onChange={(e) =>
                    setProfile({
                      ...profile,
                      notificationPreferences: {
                        ...profile.notificationPreferences,
                        emailAlerts: e.target.checked,
                      },
                    })
                  }
                  className="rounded text-blue-600 focus:ring-blue-500 w-4 h-4"
                />
                <span className="text-gray-700 font-medium">Send Email Notifications</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={profile.notificationPreferences.overdueReminders}
                  onChange={(e) =>
                    setProfile({
                      ...profile,
                      notificationPreferences: {
                        ...profile.notificationPreferences,
                        overdueReminders: e.target.checked,
                      },
                    })
                  }
                  className="rounded text-blue-600 focus:ring-blue-500 w-4 h-4"
                />
                <span className="text-gray-700 font-medium">Automated Overdue Rental Reminders</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={profile.notificationPreferences.maintenanceAlerts}
                  onChange={(e) =>
                    setProfile({
                      ...profile,
                      notificationPreferences: {
                        ...profile.notificationPreferences,
                        maintenanceAlerts: e.target.checked,
                      },
                    })
                  }
                  className="rounded text-blue-600 focus:ring-blue-500 w-4 h-4"
                />
                <span className="text-gray-700 font-medium">Caterpillar Product Link™ Maintenance Alerts</span>
              </label>
            </div>
          </div>

          <div className="pt-4 border-t border-gray-100 flex items-center justify-end">
            <button
              type="submit"
              className="inline-flex items-center gap-2 px-5 py-2.5 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow-xs transition-colors"
            >
              <Save className="w-4 h-4" /> Save Profile Settings
            </button>
          </div>
        </div>
      </form>

      {/* Logout Dialog */}
      <ConfirmDialog
        isOpen={isLogoutOpen}
        onClose={() => setIsLogoutOpen(false)}
        onConfirm={handleConfirmLogout}
        title="Sign Out of Customer Portal"
        message="Are you sure you want to end your current session?"
        confirmLabel="Sign Out"
        isDanger={true}
      />

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
};
