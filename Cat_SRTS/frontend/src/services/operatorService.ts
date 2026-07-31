import { Equipment, Operator } from '../types';
import { apiClient } from './api';
import { equipmentService } from './equipmentService';

type BackendOperator = {
  operatorId: string;
  operatorName: string;
  licenseNumber?: string;
  phoneNumber?: string;
  assignedEquipmentId?: string | null;
};

/**
 * Map one operator, resolving its machine's name from a lookup built by the
 * caller.
 *
 * The lookup is a parameter rather than a fetch because this runs once per row.
 * Fetching the equipment list in here made a single `getAll()` cost one request
 * per operator — the list is the same every time, so it is fetched once above.
 */
export const mapOperatorFromApi = (item: BackendOperator, equipmentById?: Map<string, Equipment>): Operator => {
  const equipment = item.assignedEquipmentId ? equipmentById?.get(item.assignedEquipmentId) : undefined;
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

/** Index a machine list by id, for the row mappers above and in sibling services. */
export const indexById = <T extends { id: string }>(items: T[]) =>
  new Map(items.map((item) => [item.id, item]));

/** Resolve one operator on its own — the POST/PUT paths, where one row is one row. */
const mapOne = async (item: BackendOperator): Promise<Operator> =>
  mapOperatorFromApi(item, indexById(await equipmentService.getAll()));

const toApiPayload = (operator: Partial<Operator>) => ({
  operatorId: operator.id,
  operatorName: operator.name,
  assignedEquipment: operator.assignedEquipmentId || null,
  licenseNumber: operator.licenseNumber,
  phoneNumber: operator.phoneNumber,
});

export const operatorService = {
  async getAll(): Promise<Operator[]> {
    const [response, equipment] = await Promise.all([
      apiClient.get<BackendOperator[]>('/api/operators'),
      equipmentService.getAll(),
    ]);
    const equipmentById = indexById(equipment);
    return response.data.map((item) => mapOperatorFromApi(item, equipmentById));
  },

  async add(operator: Omit<Operator, 'id'> & { id?: string }): Promise<Operator> {
    const response = await apiClient.post<BackendOperator>('/api/operators', toApiPayload(operator));
    return mapOne(response.data);
  },

  async update(id: string, updates: Partial<Operator>): Promise<Operator> {
    const response = await apiClient.put<BackendOperator>(`/api/operators/${id}`, toApiPayload(updates));
    return mapOne(response.data);
  },

  async delete(id: string): Promise<boolean> {
    await apiClient.delete(`/api/operators/${id}`);
    return true;
  },
};
