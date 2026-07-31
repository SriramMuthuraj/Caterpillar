import { SystemAlert } from '../types';
import { apiClient } from './api';

type BackendAlert = {
  type: 'RETURN_DUE' | 'EXCESSIVE_IDLE' | 'MAINTENANCE_REQUIRED';
  equipmentId: string;
  equipmentName: string;
  message: string;
};

const dismissed = new Set<string>();
const read = new Set<string>();

const fromApi = (alert: BackendAlert, index: number): SystemAlert => {
  const id = `${alert.type}-${alert.equipmentId}-${index}`;
  const type =
    alert.type === 'RETURN_DUE'
      ? 'Return Due'
      : alert.type === 'MAINTENANCE_REQUIRED'
      ? 'Maintenance Reminder'
      : 'Idle Equipment';
  return {
    id,
    title: type,
    type,
    severity: alert.type === 'RETURN_DUE' ? 'Danger' : alert.type === 'MAINTENANCE_REQUIRED' ? 'Warning' : 'Info',
    equipmentId: alert.equipmentId,
    equipmentName: alert.equipmentName,
    message: alert.message,
    timestamp: new Date().toISOString().slice(0, 16).replace('T', ' '),
    isRead: read.has(id),
    actionRequired: alert.type === 'MAINTENANCE_REQUIRED' ? 'Schedule maintenance' : undefined,
  };
};

export const alertService = {
  async getAll(): Promise<SystemAlert[]> {
    const response = await apiClient.get<BackendAlert[]>('/api/alerts');
    return response.data.map(fromApi).filter((alert) => !dismissed.has(alert.id));
  },

  async markAsRead(id: string): Promise<SystemAlert> {
    read.add(id);
    const alert = (await this.getAll()).find((item) => item.id === id);
    if (!alert) throw new Error(`Alert ${id} not found`);
    return alert;
  },

  async dismiss(id: string): Promise<boolean> {
    dismissed.add(id);
    return true;
  },
};
