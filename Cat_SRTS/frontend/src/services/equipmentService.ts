import { Equipment } from '../types';
import { apiClient } from './api';

type BackendEquipment = {
  _id?: string;
  equipmentId: string;
  equipmentName: string;
  category: Equipment['category'];
  manufacturer?: string;
  horsePower?: number;
  ownershipStatus: 'Rented' | 'Owned';
  lastUsedDate?: string | null;
  expectedReturnDate?: string | null;
  currentStatus: 'Available' | 'Assigned' | 'Working' | 'Idle' | 'Returned';
};

const toDateInput = (value?: string | null) => (value ? value.slice(0, 10) : 'N/A');

export const mapEquipmentFromApi = (item: BackendEquipment): Equipment => ({
  id: item.equipmentId,
  name: item.equipmentName,
  category: item.category,
  manufacturer: item.manufacturer || 'Caterpillar',
  horsePower: item.horsePower || 0,
  ownership: item.ownershipStatus === 'Rented' ? 'Rental' : 'Owned',
  expectedReturnDate: toDateInput(item.expectedReturnDate),
  currentStatus: item.currentStatus === 'Available' ? 'Inactive' : item.currentStatus === 'Assigned' ? 'Active' : item.currentStatus,
  dealerName: 'Empire Cat Equipment Dealer',
  dailyRate: item.ownershipStatus === 'Rented' ? 450 : 0,
});

const toApiPayload = (item: Partial<Equipment>) => ({
  equipmentId: item.id,
  equipmentName: item.name,
  category: item.category,
  manufacturer: item.manufacturer,
  horsePower: item.horsePower,
  ownershipStatus: item.ownership === 'Rental' ? 'Rented' : item.ownership,
  expectedReturnDate: item.expectedReturnDate && item.expectedReturnDate !== 'N/A' ? item.expectedReturnDate : null,
  currentStatus:
    item.currentStatus === 'Active'
      ? 'Working'
      : item.currentStatus === 'Inactive' || item.currentStatus === 'Maintenance'
      ? 'Available'
      : item.currentStatus,
});

export const equipmentService = {
  async getAll(): Promise<Equipment[]> {
    const response = await apiClient.get<BackendEquipment[]>('/api/equipment');
    return response.data.map(mapEquipmentFromApi);
  },

  async getById(id: string): Promise<Equipment | undefined> {
    const response = await apiClient.get<BackendEquipment>(`/api/equipment/${id}`);
    return mapEquipmentFromApi(response.data);
  },

  async add(item: Omit<Equipment, 'id'> & { id?: string }): Promise<Equipment> {
    const response = await apiClient.post<BackendEquipment>('/api/equipment', toApiPayload(item));
    return mapEquipmentFromApi(response.data);
  },

  async update(id: string, updates: Partial<Equipment>): Promise<Equipment> {
    const response = await apiClient.put<BackendEquipment>(`/api/equipment/${id}`, toApiPayload(updates));
    return mapEquipmentFromApi(response.data);
  },

  async delete(id: string): Promise<boolean> {
    await apiClient.delete(`/api/equipment/${id}`);
    return true;
  },
};
