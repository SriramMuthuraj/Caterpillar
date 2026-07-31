import { Equipment } from '../types';
import { equipmentService } from './equipmentService';

export const assetService = {
  async getAssets(query?: string, category?: string, status?: string, ownership?: string): Promise<Equipment[]> {
    let items = await equipmentService.getAll();

    if (query && query.trim() !== '') {
      const q = query.toLowerCase().trim();
      items = items.filter(
        (e) =>
          e.name.toLowerCase().includes(q) ||
          e.id.toLowerCase().includes(q) ||
          e.manufacturer.toLowerCase().includes(q) ||
          (e.assignedOperatorName && e.assignedOperatorName.toLowerCase().includes(q))
      );
    }

    if (category && category !== 'All') {
      items = items.filter((e) => e.category === category);
    }

    if (status && status !== 'All') {
      items = items.filter((e) => e.currentStatus === status);
    }

    if (ownership && ownership !== 'All') {
      items = items.filter((e) => e.ownership === ownership);
    }

    return items;
  },
};
