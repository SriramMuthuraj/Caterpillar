import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from '../components/layouts/MainLayout';
import { DashboardPage } from '../pages/DashboardPage';
import { EquipmentRegistrationPage } from '../pages/EquipmentRegistrationPage';
import { OperatorRegistrationPage } from '../pages/OperatorRegistrationPage';
import { EquipmentAssignmentPage } from '../pages/EquipmentAssignmentPage';
import { AssetManagementPage } from '../pages/AssetManagementPage';
import { UsageLoggingPage } from '../pages/UsageLoggingPage';
import { AlertsPage } from '../pages/AlertsPage';
import { ForecastPage } from '../pages/ForecastPage';
import { AnomaliesPage } from '../pages/AnomaliesPage';
import { ProfilePage } from '../pages/ProfilePage';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/registration/equipment" element={<EquipmentRegistrationPage />} />
        <Route path="/registration/operators" element={<OperatorRegistrationPage />} />
        <Route path="/registration/assignment" element={<EquipmentAssignmentPage />} />
        <Route path="/assets" element={<AssetManagementPage />} />
        <Route path="/usage" element={<UsageLoggingPage />} />
        <Route path="/forecast" element={<ForecastPage />} />
        <Route path="/anomalies" element={<AnomaliesPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
};
