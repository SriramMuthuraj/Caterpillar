import React, { useState, useEffect } from 'react';
import { UserPlus, Edit2, Trash2, UserCheck, Phone, Shield } from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { SearchInput } from '../components/ui/SearchInput';
import { Modal } from '../components/ui/Modal';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { Toast, ToastMessage } from '../components/ui/Toast';
import { operatorService } from '../services/operatorService';
import { equipmentService } from '../services/equipmentService';
import { Operator, Equipment } from '../types';

export const OperatorRegistrationPage: React.FC = () => {
  const [operators, setOperators] = useState<Operator[]>([]);
  const [equipmentList, setEquipmentList] = useState<Equipment[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const [toast, setToast] = useState<ToastMessage | null>(null);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingOperator, setEditingOperator] = useState<Operator | null>(null);

  // Form Fields
  const [formData, setFormData] = useState({
    id: '',
    name: '',
    assignedEquipmentId: '',
    assignedEquipmentName: '',
    licenseNumber: '',
    phoneNumber: '',
    experienceYears: 5,
    status: 'Active' as 'Active' | 'On Leave' | 'Unassigned',
  });

  // Delete State
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    const [ops, eqList] = await Promise.all([operatorService.getAll(), equipmentService.getAll()]);
    setOperators(ops);
    setEquipmentList(eqList);
    setLoading(false);
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleOpenAdd = () => {
    setEditingOperator(null);
    setFormData({
      id: `OP-${Math.floor(200 + Math.random() * 800)}`,
      name: '',
      assignedEquipmentId: '',
      assignedEquipmentName: '',
      licenseNumber: 'HV-CAT-' + Math.floor(10000 + Math.random() * 90000) + '-AZ',
      phoneNumber: '+1 (555) ' + Math.floor(100 + Math.random() * 900) + '-' + Math.floor(1000 + Math.random() * 9000),
      experienceYears: 5,
      status: 'Active',
    });
    setIsModalOpen(true);
  };

  const handleOpenEdit = (op: Operator) => {
    setEditingOperator(op);
    setFormData({
      id: op.id,
      name: op.name,
      assignedEquipmentId: op.assignedEquipmentId || '',
      assignedEquipmentName: op.assignedEquipmentName || '',
      licenseNumber: op.licenseNumber,
      phoneNumber: op.phoneNumber,
      experienceYears: op.experienceYears || 5,
      status: op.status,
    });
    setIsModalOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) return;

    // Find assigned equipment name if ID chosen
    let eqName = formData.assignedEquipmentName;
    if (formData.assignedEquipmentId) {
      const selectedEq = equipmentList.find((e) => e.id === formData.assignedEquipmentId);
      if (selectedEq) eqName = selectedEq.name;
    }

    const payload = {
      ...formData,
      assignedEquipmentName: eqName,
    };

    if (editingOperator) {
      await operatorService.update(editingOperator.id, payload);
      setToast({
        id: Date.now().toString(),
        type: 'success',
        title: 'Operator Updated',
        message: `${formData.name} was successfully updated.`,
      });
    } else {
      await operatorService.add(payload);
      setToast({
        id: Date.now().toString(),
        type: 'success',
        title: 'Operator Registered',
        message: `${formData.name} was successfully registered.`,
      });
    }

    setIsModalOpen(false);
    loadData();
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    await operatorService.delete(deleteId);
    setToast({
      id: Date.now().toString(),
      type: 'info',
      title: 'Operator Deleted',
      message: `Operator record ${deleteId} has been removed.`,
    });
    setDeleteId(null);
    loadData();
  };

  const filteredOperators = operators.filter((op) => {
    const q = search.toLowerCase();
    return (
      op.name.toLowerCase().includes(q) ||
      op.id.toLowerCase().includes(q) ||
      op.licenseNumber.toLowerCase().includes(q) ||
      (op.assignedEquipmentName && op.assignedEquipmentName.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Operator Registration"
        description="Manage heavy machinery operators, certified license numbers, and active equipment assignments."
        action={
          <button
            onClick={handleOpenAdd}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow-xs transition-colors"
          >
            <UserPlus className="w-4 h-4" />
            Register Operator
          </button>
        }
      />

      {/* Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="w-full md:w-96">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search by operator name, ID, license or equipment..."
          />
        </div>
        <div className="text-xs text-gray-500 font-medium">
          Total Operators: <span className="font-bold text-gray-900">{operators.length}</span>
        </div>
      </div>

      {/* Operator Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-500 uppercase text-[10px] tracking-wider border-b border-gray-200">
              <tr>
                <th className="px-4 py-3.5 font-bold">Operator ID</th>
                <th className="px-4 py-3.5 font-bold">Operator Name</th>
                <th className="px-4 py-3.5 font-bold">Assigned Equipment</th>
                <th className="px-4 py-3.5 font-bold">License Number</th>
                <th className="px-4 py-3.5 font-bold">Phone Number</th>
                <th className="px-4 py-3.5 font-bold">Status</th>
                <th className="px-4 py-3.5 font-bold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-gray-500">
                    Loading certified operator roster...
                  </td>
                </tr>
              ) : filteredOperators.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-12 text-center text-gray-500">
                    <UserCheck className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                    No operator records match your search criteria.
                  </td>
                </tr>
              ) : (
                filteredOperators.map((op) => (
                  <tr key={op.id} className="hover:bg-gray-50/80 transition-colors">
                    <td className="px-4 py-3.5 font-mono font-semibold text-blue-600">{op.id}</td>
                    <td className="px-4 py-3.5 font-bold text-gray-900">{op.name}</td>
                    <td className="px-4 py-3.5">
                      {op.assignedEquipmentName ? (
                        <div className="font-medium text-gray-900">{op.assignedEquipmentName}</div>
                      ) : (
                        <span className="text-gray-400 italic">Unassigned</span>
                      )}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-gray-700 flex items-center gap-1.5">
                      <Shield className="w-3.5 h-3.5 text-blue-500" />
                      {op.licenseNumber}
                    </td>
                    <td className="px-4 py-3.5 text-gray-700">
                      <div className="flex items-center gap-1.5">
                        <Phone className="w-3.5 h-3.5 text-gray-400" />
                        {op.phoneNumber}
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-semibold border ${
                          op.status === 'Active'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : op.status === 'On Leave'
                            ? 'bg-amber-50 text-amber-700 border-amber-200'
                            : 'bg-gray-50 text-gray-600 border-gray-200'
                        }`}
                      >
                        {op.status}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-right space-x-1">
                      <button
                        onClick={() => handleOpenEdit(op)}
                        className="p-1.5 text-gray-500 hover:text-blue-600 rounded-md hover:bg-gray-100 transition-colors"
                        title="Edit Operator"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setDeleteId(op.id)}
                        className="p-1.5 text-gray-500 hover:text-red-600 rounded-md hover:bg-gray-100 transition-colors"
                        title="Delete Operator"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add / Edit Operator Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingOperator ? 'Edit Operator Record' : 'Register New Operator'}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Operator ID</label>
              <input
                type="text"
                required
                value={formData.id}
                onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Operator Full Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Marcus Vance"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">License Number</label>
              <input
                type="text"
                required
                placeholder="e.g. HV-CAT-88910-AZ"
                value={formData.licenseNumber}
                onChange={(e) => setFormData({ ...formData, licenseNumber: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Phone Number</label>
              <input
                type="text"
                required
                placeholder="+1 (555) 234-5678"
                value={formData.phoneNumber}
                onChange={(e) => setFormData({ ...formData, phoneNumber: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Assigned Equipment</label>
              <select
                value={formData.assignedEquipmentId}
                onChange={(e) => setFormData({ ...formData, assignedEquipmentId: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
              >
                <option value="">-- Unassigned --</option>
                {equipmentList.map((eq) => (
                  <option key={eq.id} value={eq.id}>
                    {eq.id} - {eq.name} ({eq.category})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Status</label>
              <select
                value={formData.status}
                onChange={(e) =>
                  setFormData({ ...formData, status: e.target.value as 'Active' | 'On Leave' | 'Unassigned' })
                }
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
              >
                <option value="Active">Active</option>
                <option value="On Leave">On Leave</option>
                <option value="Unassigned">Unassigned</option>
              </select>
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
              {editingOperator ? 'Save Changes' : 'Register Operator'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={deleteId !== null}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="Delete Operator Record"
        message={`Are you sure you want to delete operator ${deleteId}?`}
      />

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
};
