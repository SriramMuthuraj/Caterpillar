import { EquipmentAssignment } from '../types';
import { apiClient } from './api';
import { equipmentService } from './equipmentService';
import { operatorService } from './operatorService';

type BackendAssignment = {
  assignmentId: string;
  equipmentId: string;
  operatorId: string;
  siteName: string;
  checkOutTime: string;
  checkInTime?: string | null;
  status: 'Assigned' | 'Working' | 'Idle' | 'Returned';
};

const toDateInput = (value?: string | null) => (value ? value.slice(0, 10) : '');

const fromApi = async (item: BackendAssignment): Promise<EquipmentAssignment> => {
  const [equipment, operators] = await Promise.all([equipmentService.getAll(), operatorService.getAll()]);
  const eq = equipment.find((entry) => entry.id === item.equipmentId);
  const op = operators.find((entry) => entry.id === item.operatorId);
  return {
    id: item.assignmentId,
    equipmentId: item.equipmentId,
    equipmentName: eq?.name || item.equipmentId,
    operatorId: item.operatorId,
    operatorName: op?.name || item.operatorId,
    siteName: item.siteName,
    checkOutDate: toDateInput(item.checkOutTime),
    checkInDate: toDateInput(item.checkInTime),
    status: item.status === 'Returned' ? 'Completed' : item.status === 'Idle' ? 'Pending Return' : 'Assigned',
  };
};

const toApiPayload = (assignment: Partial<EquipmentAssignment>) => ({
  assignmentId: assignment.id,
  equipmentId: assignment.equipmentId,
  operatorId: assignment.operatorId,
  siteName: assignment.siteName,
  checkOutTime: assignment.checkOutDate,
  checkInTime: assignment.checkInDate || null,
  status:
    assignment.status === 'Completed'
      ? 'Returned'
      : assignment.status === 'Pending Return'
      ? 'Idle'
      : assignment.status === 'Unassigned'
      ? 'Idle'
      : assignment.status,
});

export const assignmentService = {
  async getAll(): Promise<EquipmentAssignment[]> {
    const response = await apiClient.get<BackendAssignment[]>('/api/assignments');
    return Promise.all(response.data.map(fromApi));
  },

  async add(assignment: Omit<EquipmentAssignment, 'id'> & { id?: string }): Promise<EquipmentAssignment> {
    const response = await apiClient.post<BackendAssignment>('/api/assignments', toApiPayload(assignment));
    return fromApi(response.data);
  },

  async update(id: string, updates: Partial<EquipmentAssignment>): Promise<EquipmentAssignment> {
    const response = await apiClient.put<BackendAssignment>(`/api/assignments/${id}`, toApiPayload(updates));
    return fromApi(response.data);
  },

  async delete(id: string): Promise<boolean> {
    await apiClient.delete(`/api/assignments/${id}`);
    return true;
  },
};
