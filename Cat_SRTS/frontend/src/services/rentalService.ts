import { RentalRecord } from '../types';
import { assignmentService } from './assignmentService';

const rentalFromAssignment = (assignment: Awaited<ReturnType<typeof assignmentService.getAll>>[number]): RentalRecord => ({
  id: assignment.id,
  equipmentId: assignment.equipmentId,
  equipmentName: assignment.equipmentName,
  dealerName: 'Empire Cat Equipment Dealer',
  startDate: assignment.checkOutDate,
  expectedReturnDate: assignment.checkInDate || 'N/A',
  actualReturnDate: assignment.status === 'Completed' ? assignment.checkInDate : undefined,
  dailyRate: 450,
  totalCost: 450,
  status: assignment.status === 'Completed' ? 'Returned' : assignment.status === 'Pending Return' ? 'Idle' : 'Working',
  operatorName: assignment.operatorName,
  siteName: assignment.siteName,
});

export const rentalService = {
  async getAll(): Promise<RentalRecord[]> {
    const assignments = await assignmentService.getAll();
    return assignments.map(rentalFromAssignment);
  },

  async checkOut(rental: Omit<RentalRecord, 'id' | 'status'>): Promise<RentalRecord> {
    const assignment = await assignmentService.add({
      id: `ASG-${Math.floor(1000 + Math.random() * 9000)}`,
      equipmentId: rental.equipmentId,
      equipmentName: rental.equipmentName,
      operatorId: 'OP-001',
      operatorName: rental.operatorName,
      siteName: rental.siteName,
      checkOutDate: rental.startDate,
      checkInDate: rental.expectedReturnDate,
      status: 'Assigned',
    });
    return rentalFromAssignment(assignment);
  },

  async checkIn(id: string, returnDate: string): Promise<RentalRecord> {
    const assignment = await assignmentService.update(id, {
      checkInDate: returnDate,
      status: 'Completed',
    });
    return rentalFromAssignment(assignment);
  },

  async updateStatus(id: string, status: 'Working' | 'Idle' | 'Returned'): Promise<RentalRecord> {
    const assignment = await assignmentService.update(id, {
      status: status === 'Returned' ? 'Completed' : status === 'Idle' ? 'Pending Return' : 'Assigned',
    });
    return rentalFromAssignment(assignment);
  },
};
