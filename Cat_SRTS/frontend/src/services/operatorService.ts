import { Operator } from '../types';
import { apiClient } from './api';
import { equipmentService } from './equipmentService';

type BackendOperator = {
  operatorId: string;
  operatorName: string;
  licenseNumber?: string;
  phoneNumber?: string;
  assignedEquipmentId?: string | null;
};

export const mapOperatorFromApi = async (item: BackendOperator): Promise<Operator> => {
  const equipment = item.assignedEquipmentId ? (await equipmentService.getAll()).find((eq) => eq.id === item.assignedEquipmentId) : undefined;
  return {
    id: item.operatorId,
    name: item.operatorName,
    assignedEquipmentId: item.assignedEquipmentId || '',
    assignedEquipmentName: equipment?.name || '',
    licenseNumber: item.licenseNumber || '',
    phoneNumber: item.phoneNumber || '',
    status: item.assignedEquipmentId ? 'Active' : 'Unassigned',
  };
};

const toApiPayload = (operator: Partial<Operator>) => ({
  operatorId: operator.id,
  operatorName: operator.name,
  assignedEquipment: operator.assignedEquipmentId || null,
  licenseNumber: operator.licenseNumber,
  phoneNumber: operator.phoneNumber,
});

export const operatorService = {
  async getAll(): Promise<Operator[]> {
    const response = await apiClient.get<BackendOperator[]>('/api/operators');
    return Promise.all(response.data.map(mapOperatorFromApi));
  },

  async add(operator: Omit<Operator, 'id'> & { id?: string }): Promise<Operator> {
    const response = await apiClient.post<BackendOperator>('/api/operators', toApiPayload(operator));
    return mapOperatorFromApi(response.data);
  },

  async update(id: string, updates: Partial<Operator>): Promise<Operator> {
    const response = await apiClient.put<BackendOperator>(`/api/operators/${id}`, toApiPayload(updates));
    return mapOperatorFromApi(response.data);
  },

  async delete(id: string): Promise<boolean> {
    await apiClient.delete(`/api/operators/${id}`);
    return true;
  },
};
