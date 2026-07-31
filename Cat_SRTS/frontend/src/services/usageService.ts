import { Equipment, Operator, UsageLog } from '../types';
import { apiClient } from './api';
import { equipmentService } from './equipmentService';
import { indexById, operatorService } from './operatorService';

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

/**
 * Map one usage row against pre-built lookups.
 *
 * Synchronous on purpose. This runs once per log line — there are ~1,900 of
 * them — so fetching the equipment and operator lists in here turned one page
 * load into hundreds of thousands of requests that never finished.
 */
const fromApi = (
  item: BackendUsageLog,
  equipmentById: Map<string, Equipment>,
  operatorsById: Map<string, Operator>,
): UsageLog => {
  const eq = equipmentById.get(item.equipmentId);
  const op = operatorsById.get(item.operatorId);
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

/** Fetch both reference lists once and index them. Two requests, not two per row. */
const lookups = async (): Promise<[Map<string, Equipment>, Map<string, Operator>]> => {
  const [equipment, operators] = await Promise.all([equipmentService.getAll(), operatorService.getAll()]);
  return [indexById(equipment), indexById(operators)];
};

/** Map a single row — the POST path, where the fan-out cost does not arise. */
const mapOne = async (item: BackendUsageLog): Promise<UsageLog> => {
  const [equipmentById, operatorsById] = await lookups();
  return fromApi(item, equipmentById, operatorsById);
};

const resolveOperatorId = async (operatorName: string) => {
  const operators = await operatorService.getAll();
  return operators.find((operator) => operator.name === operatorName)?.id || operators[0]?.id || 'OP-001';
};

export const usageService = {
  async getAll(): Promise<UsageLog[]> {
    const [response, [equipmentById, operatorsById]] = await Promise.all([
      apiClient.get<BackendUsageLog[]>('/api/usage'),
      lookups(),
    ]);
    return response.data.map((item) => fromApi(item, equipmentById, operatorsById));
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
    return mapOne(response.data);
  },
};
