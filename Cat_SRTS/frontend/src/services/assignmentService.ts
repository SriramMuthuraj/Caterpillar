import { Equipment, EquipmentAssignment, Operator } from '../types';
import { apiClient } from './api';
import { equipmentService } from './equipmentService';
import { indexById, operatorService } from './operatorService';

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

/** Map one assignment against pre-built lookups — see the note in usageService. */
const fromApi = (
  item: BackendAssignment,
  equipmentById: Map<string, Equipment>,
  operatorsById: Map<string, Operator>,
): EquipmentAssignment => {
  const eq = equipmentById.get(item.equipmentId);
  const op = operatorsById.get(item.operatorId);
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

const lookups = async (): Promise<[Map<string, Equipment>, Map<string, Operator>]> => {
  const [equipment, operators] = await Promise.all([equipmentService.getAll(), operatorService.getAll()]);
  return [indexById(equipment), indexById(operators)];
};

const mapOne = async (item: BackendAssignment): Promise<EquipmentAssignment> => {
  const [equipmentById, operatorsById] = await lookups();
  return fromApi(item, equipmentById, operatorsById);
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
    const [response, [equipmentById, operatorsById]] = await Promise.all([
      apiClient.get<BackendAssignment[]>('/api/assignments'),
      lookups(),
    ]);
    return response.data.map((item) => fromApi(item, equipmentById, operatorsById));
  },

  async add(assignment: Omit<EquipmentAssignment, 'id'> & { id?: string }): Promise<EquipmentAssignment> {
    const response = await apiClient.post<BackendAssignment>('/api/assignments', toApiPayload(assignment));
    return mapOne(response.data);
  },

  async update(id: string, updates: Partial<EquipmentAssignment>): Promise<EquipmentAssignment> {
    const response = await apiClient.put<BackendAssignment>(`/api/assignments/${id}`, toApiPayload(updates));
    return mapOne(response.data);
  },

  async delete(id: string): Promise<boolean> {
    await apiClient.delete(`/api/assignments/${id}`);
    return true;
  },
};
