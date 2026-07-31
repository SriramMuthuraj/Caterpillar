import { UsageLog } from '../types';
import { apiClient } from './api';
import { equipmentService } from './equipmentService';
import { operatorService } from './operatorService';

type BackendUsageLog = {
  _id?: string;
  usageId?: string;
  equipmentId: string;
  operatorId: string;
  runtimeHours: number;
  fuelUsage: number;
  idleHours: number;
  location: string;
  usageDate: string;
};

const efficiency = (runtime: number, idle: number) => Math.round((runtime / Math.max(runtime + idle, 1)) * 100);

const fromApi = async (item: BackendUsageLog): Promise<UsageLog> => {
  const [equipment, operators] = await Promise.all([equipmentService.getAll(), operatorService.getAll()]);
  const eq = equipment.find((entry) => entry.id === item.equipmentId);
  const op = operators.find((entry) => entry.id === item.operatorId);
  return {
    id: item.usageId || item._id || item.equipmentId,
    equipmentId: item.equipmentId,
    equipmentName: eq?.name || item.equipmentId,
    date: item.usageDate.slice(0, 10),
    runtimeHours: item.runtimeHours,
    fuelUsageLiters: item.fuelUsage,
    idleHours: item.idleHours,
    location: item.location,
    operatorName: op?.name || item.operatorId,
    efficiencyScore: efficiency(item.runtimeHours, item.idleHours),
  };
};

const resolveOperatorId = async (operatorName: string) => {
  const operators = await operatorService.getAll();
  return operators.find((operator) => operator.name === operatorName)?.id || operators[0]?.id || 'OP-001';
};

export const usageService = {
  async getAll(): Promise<UsageLog[]> {
    const response = await apiClient.get<BackendUsageLog[]>('/api/usage');
    return Promise.all(response.data.map(fromApi));
  },

  async getSummary() {
    const usageLogs = await this.getAll();
    const totalRuntime = usageLogs.reduce((acc, curr) => acc + curr.runtimeHours, 0);
    const totalFuel = usageLogs.reduce((acc, curr) => acc + curr.fuelUsageLiters, 0);
    const totalIdle = usageLogs.reduce((acc, curr) => acc + curr.idleHours, 0);
    const avgScore = Math.round(
      usageLogs.reduce((acc, curr) => acc + curr.efficiencyScore, 0) / (usageLogs.length || 1)
    );

    return {
      totalRuntimeHours: totalRuntime,
      totalFuelLiters: totalFuel,
      totalIdleHours: totalIdle,
      avgEfficiencyScore: avgScore,
    };
  },

  async addLog(log: Omit<UsageLog, 'id'>): Promise<UsageLog> {
    const response = await apiClient.post<BackendUsageLog>('/api/usage', {
      equipmentId: log.equipmentId,
      operatorId: await resolveOperatorId(log.operatorName),
      runtimeHours: log.runtimeHours,
      fuelUsage: log.fuelUsageLiters,
      idleHours: log.idleHours,
      location: log.location,
      usageDate: log.date,
    });
    return fromApi(response.data);
  },
};
