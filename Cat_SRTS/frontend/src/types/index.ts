export type EquipmentStatus = 'Active' | 'Inactive' | 'Maintenance' | 'Working' | 'Idle' | 'Returned';
export type OwnershipType = 'Rental' | 'Owned';
export type CategoryType = 'Excavator' | 'Dozer' | 'Wheel Loader' | 'Dump Truck' | 'Compactor' | 'Motor Grader';

export interface Equipment {
  id: string; // e.g. "EQ-1001"
  name: string; // e.g. "Cat 320 Hydraulic Excavator"
  category: CategoryType;
  manufacturer: string; // e.g. "Caterpillar"
  horsePower: number; // e.g. 172
  ownership: OwnershipType;
  expectedReturnDate: string; // YYYY-MM-DD or N/A for owned
  currentStatus: EquipmentStatus;
  serialNumber?: string;
  modelYear?: number;
  assignedOperatorId?: string;
  assignedOperatorName?: string;
  assignedSite?: string;
  dailyRate?: number;
  dealerName?: string;
}

export interface Operator {
  id: string; // e.g. "OP-201"
  name: string;
  assignedEquipmentId?: string;
  assignedEquipmentName?: string;
  licenseNumber: string;
  phoneNumber: string;
  experienceYears?: number;
  status: 'Active' | 'On Leave' | 'Unassigned';
}

export interface EquipmentAssignment {
  id: string; // e.g. "ASG-501"
  equipmentId: string;
  equipmentName: string;
  operatorId: string;
  operatorName: string;
  siteName: string;
  checkOutDate: string; // YYYY-MM-DD
  checkInDate: string; // YYYY-MM-DD
  status: 'Assigned' | 'Unassigned' | 'Pending Return' | 'Completed';
  notes?: string;
}

export interface RentalRecord {
  id: string; // e.g. "RNT-801"
  equipmentId: string;
  equipmentName: string;
  dealerName: string;
  startDate: string;
  expectedReturnDate: string;
  actualReturnDate?: string;
  dailyRate: number;
  totalCost: number;
  status: 'Working' | 'Idle' | 'Returned';
  operatorName: string;
  siteName: string;
}

export interface UsageLog {
  id: string;
  equipmentId: string;
  equipmentName: string;
  date: string;
  runtimeHours: number;
  fuelUsageLiters: number;
  idleHours: number;
  location: string;
  operatorName: string;
  efficiencyScore: number; // 0-100%
}

export interface ReportSummary {
  totalRuntimeHours: number;
  totalFuelLiters: number;
  avgUtilizationRate: number;
  totalRentalExpense: number;
  idleTimePercentage: number;
}

export type AlertSeverity = 'Danger' | 'Warning' | 'Info';
export type AlertType = 'Return Due' | 'Overdue' | 'Maintenance Reminder' | 'Idle Equipment';

export interface SystemAlert {
  id: string;
  title: string;
  type: AlertType;
  severity: AlertSeverity;
  equipmentId: string;
  equipmentName: string;
  message: string;
  timestamp: string;
  isRead: boolean;
  actionRequired?: string;
}

export interface CustomerProfile {
  id: string;
  name: string;
  email: string;
  phone: string;
  role: string;
  companyName: string;
  taxId: string;
  accountNumber: string;
  primaryDealer: string;
  billingAddress: string;
  defaultSite: string;
  notificationPreferences: {
    emailAlerts: boolean;
    smsAlerts: boolean;
    overdueReminders: boolean;
    maintenanceAlerts: boolean;
  };
  timezone: string;
  language: string;
}

export interface ActivityItem {
  id: string;
  title: string;
  description: string;
  timestamp: string;
  type: 'equipment' | 'assignment' | 'rental' | 'alert' | 'operator';
}
