import React, { useState, useEffect } from 'react';
import { Link2, Plus, Edit2, MapPin, Calendar, CheckCircle2 } from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { SearchInput } from '../components/ui/SearchInput';
import { Modal } from '../components/ui/Modal';
import { StatusBadge } from '../components/ui/StatusBadge';
import { Toast, ToastMessage } from '../components/ui/Toast';
import { assignmentService } from '../services/assignmentService';
import { equipmentService } from '../services/equipmentService';
import { operatorService } from '../services/operatorService';
import { EquipmentAssignment, Equipment, Operator } from '../types';

export const EquipmentAssignmentPage: React.FC = () => {
  const [assignments, setAssignments] = useState<EquipmentAssignment[]>([]);
  const [equipmentList, setEquipmentList] = useState<Equipment[]>([]);
  const [operatorsList, setOperatorsList] = useState<Operator[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const [toast, setToast] = useState<ToastMessage | null>(null);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingAssignment, setEditingAssignment] = useState<EquipmentAssignment | null>(null);

  // Form Fields
  const [formData, setFormData] = useState({
    id: '',
    equipmentId: '',
    equipmentName: '',
    operatorId: '',
    operatorName: '',
    siteName: 'Apex Mine Site A',
    checkOutDate: '2026-07-30',
    checkInDate: '2026-08-30',
    status: 'Assigned' as 'Assigned' | 'Unassigned' | 'Pending Return' | 'Completed',
    notes: '',
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const [asgs, eqList, ops] = await Promise.all([
        assignmentService.getAll(),
        equipmentService.getAll(),
        operatorService.getAll(),
      ]);
      setAssignments(asgs);
      setEquipmentList(eqList);
      setOperatorsList(ops);
    } catch (error) {
      setToast({
        id: Date.now().toString(),
        type: 'error',
        title: 'Could not load assignments',
        message: error instanceof Error ? error.message : 'The backend did not respond.',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleOpenAdd = () => {
    setEditingAssignment(null);
    const defaultEq = equipmentList[0];
    const defaultOp = operatorsList[0];

    setFormData({
      id: `ASG-${Math.floor(500 + Math.random() * 500)}`,
      equipmentId: defaultEq ? defaultEq.id : '',
      equipmentName: defaultEq ? defaultEq.name : '',
      operatorId: defaultOp ? defaultOp.id : '',
      operatorName: defaultOp ? defaultOp.name : '',
      siteName: 'Apex Mine Site A',
      checkOutDate: new Date().toISOString().split('T')[0],
      checkInDate: '2026-08-30',
      status: 'Assigned',
      notes: '',
    });
    setIsModalOpen(true);
  };

  const handleOpenEdit = (asg: EquipmentAssignment) => {
    setEditingAssignment(asg);
    setFormData({
      id: asg.id,
      equipmentId: asg.equipmentId,
      equipmentName: asg.equipmentName,
      operatorId: asg.operatorId,
      operatorName: asg.operatorName,
      siteName: asg.siteName,
      checkOutDate: asg.checkOutDate,
      checkInDate: asg.checkInDate,
      status: asg.status,
      notes: asg.notes || '',
    });
    setIsModalOpen(true);
  };

  const handleEquipmentChange = (eqId: string) => {
    const eq = equipmentList.find((e) => e.id === eqId);
    setFormData((prev) => ({
      ...prev,
      equipmentId: eqId,
      equipmentName: eq ? eq.name : prev.equipmentName,
    }));
  };

  const handleOperatorChange = (opId: string) => {
    const op = operatorsList.find((o) => o.id === opId);
    setFormData((prev) => ({
      ...prev,
      operatorId: opId,
      operatorName: op ? op.name : prev.operatorName,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (editingAssignment) {
      await assignmentService.update(editingAssignment.id, formData);
      setToast({
        id: Date.now().toString(),
        type: 'success',
        title: 'Assignment Updated',
        message: `Assignment ${formData.id} updated successfully.`,
      });
    } else {
      await assignmentService.add(formData);
      setToast({
        id: Date.now().toString(),
        type: 'success',
        title: 'Equipment Assigned',
        message: `${formData.equipmentName} assigned to ${formData.operatorName} at ${formData.siteName}.`,
      });
    }

    setIsModalOpen(false);
    loadData();
  };

  const filteredAssignments = assignments.filter((a) => {
    const q = search.toLowerCase();
    return (
      a.id.toLowerCase().includes(q) ||
      a.equipmentName.toLowerCase().includes(q) ||
      a.operatorName.toLowerCase().includes(q) ||
      a.siteName.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Equipment Assignment"
        description="Dispatch equipment to project sites, assign qualified operators, and track check-out / check-in schedules."
        action={
          <button
            onClick={handleOpenAdd}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow-xs transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Equipment Assignment
          </button>
        }
      />

      {/* Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="w-full md:w-96">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search by assignment ID, site, equipment or operator..."
          />
        </div>
        <div className="text-xs text-gray-500 font-medium">
          Active Assignments: <span className="font-bold text-gray-900">{assignments.filter((a) => a.status === 'Assigned').length}</span>
        </div>
      </div>

      {/* Assignment Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-500 uppercase text-[10px] tracking-wider border-b border-gray-200">
              <tr>
                <th className="px-4 py-3.5 font-bold">Assignment ID</th>
                <th className="px-4 py-3.5 font-bold">Equipment</th>
                <th className="px-4 py-3.5 font-bold">Operator</th>
                <th className="px-4 py-3.5 font-bold">Site Location</th>
                <th className="px-4 py-3.5 font-bold">Check-Out</th>
                <th className="px-4 py-3.5 font-bold">Check-In</th>
                <th className="px-4 py-3.5 font-bold">Status</th>
                <th className="px-4 py-3.5 font-bold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-gray-500">
                    Loading equipment assignments...
                  </td>
                </tr>
              ) : filteredAssignments.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-12 text-center text-gray-500">
                    <Link2 className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                    No assignment records match your filter.
                  </td>
                </tr>
              ) : (
                filteredAssignments.map((asg) => (
                  <tr key={asg.id} className="hover:bg-gray-50/80 transition-colors">
                    <td className="px-4 py-3.5 font-mono font-semibold text-blue-600">{asg.id}</td>
                    <td className="px-4 py-3.5">
                      <div className="font-bold text-gray-900">{asg.equipmentName}</div>
                      <div className="text-[11px] text-gray-400 font-mono">{asg.equipmentId}</div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="font-medium text-gray-900">{asg.operatorName}</div>
                      <div className="text-[11px] text-gray-400 font-mono">{asg.operatorId}</div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-1 text-gray-800 font-medium">
                        <MapPin className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
                        {asg.siteName}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-gray-600 font-mono">
                      <div className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-gray-400" />
                        {asg.checkOutDate}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-gray-600 font-mono">
                      <div className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-gray-400" />
                        {asg.checkInDate}
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <StatusBadge status={asg.status} />
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <button
                        onClick={() => handleOpenEdit(asg)}
                        className="p-1.5 text-gray-500 hover:text-blue-600 rounded-md hover:bg-gray-100 transition-colors"
                        title="Edit Assignment"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Assignment Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingAssignment ? 'Edit Assignment' : 'New Equipment Assignment'}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Equipment</label>
              <select
                value={formData.equipmentId}
                onChange={(e) => handleEquipmentChange(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
              >
                {equipmentList.map((eq) => (
                  <option key={eq.id} value={eq.id}>
                    {eq.name} ({eq.id})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Operator</label>
              <select
                value={formData.operatorId}
                onChange={(e) => handleOperatorChange(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
              >
                {operatorsList.map((op) => (
                  <option key={op.id} value={op.id}>
                    {op.name} ({op.id})
                  </option>
                ))}
              </select>
            </div>

            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-gray-700 mb-1">Project Site Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Apex Mine Site A"
                value={formData.siteName}
                onChange={(e) => setFormData({ ...formData, siteName: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Check-Out Date</label>
              <input
                type="date"
                required
                value={formData.checkOutDate}
                onChange={(e) => setFormData({ ...formData, checkOutDate: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Check-In Date</label>
              <input
                type="date"
                required
                value={formData.checkInDate}
                onChange={(e) => setFormData({ ...formData, checkInDate: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Status</label>
              <select
                value={formData.status}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    status: e.target.value as 'Assigned' | 'Unassigned' | 'Pending Return' | 'Completed',
                  })
                }
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
              >
                <option value="Assigned">Assigned</option>
                <option value="Pending Return">Pending Return</option>
                <option value="Completed">Completed</option>
                <option value="Unassigned">Unassigned</option>
              </select>
            </div>

            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-gray-700 mb-1">Operational Notes</label>
              <textarea
                rows={2}
                placeholder="Specific instructions or work scope for operator..."
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>
          </div>

          <div className="pt-4 border-t border-gray-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="px-4 py-2 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700"
            >
              {editingAssignment ? 'Save Assignment' : 'Confirm Assignment'}
            </button>
          </div>
        </form>
      </Modal>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
};
