import React, { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Filter, Truck } from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { StatusBadge } from '../components/ui/StatusBadge';
import { SearchInput } from '../components/ui/SearchInput';
import { Modal } from '../components/ui/Modal';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { Toast, ToastMessage } from '../components/ui/Toast';
import { equipmentService } from '../services/equipmentService';
import { Equipment, CategoryType, EquipmentStatus, OwnershipType } from '../types';

export const EquipmentRegistrationPage: React.FC = () => {
  const [equipmentList, setEquipmentList] = useState<Equipment[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('All');
  const [ownershipFilter, setOwnershipFilter] = useState<string>('All');

  const [toast, setToast] = useState<ToastMessage | null>(null);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingEquipment, setEditingEquipment] = useState<Equipment | null>(null);

  // Form Fields
  const [formData, setFormData] = useState({
    id: '',
    name: '',
    category: 'Excavator' as CategoryType,
    manufacturer: 'Caterpillar',
    horsePower: 200,
    ownership: 'Rental' as OwnershipType,
    expectedReturnDate: '2026-08-30',
    currentStatus: 'Active' as EquipmentStatus,
  });

  // Delete State
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    const data = await equipmentService.getAll();
    setEquipmentList(data);
    setLoading(false);
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleOpenAddModal = () => {
    setEditingEquipment(null);
    setFormData({
      id: `EQ-${Math.floor(1000 + Math.random() * 9000)}`,
      name: '',
      category: 'Excavator',
      manufacturer: 'Caterpillar',
      horsePower: 200,
      ownership: 'Rental',
      expectedReturnDate: '2026-08-30',
      currentStatus: 'Active',
    });
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (eq: Equipment) => {
    setEditingEquipment(eq);
    setFormData({
      id: eq.id,
      name: eq.name,
      category: eq.category,
      manufacturer: eq.manufacturer,
      horsePower: eq.horsePower,
      ownership: eq.ownership,
      expectedReturnDate: eq.expectedReturnDate,
      currentStatus: eq.currentStatus,
    });
    setIsModalOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) return;

    if (editingEquipment) {
      await equipmentService.update(editingEquipment.id, formData);
      setToast({
        id: Date.now().toString(),
        type: 'success',
        title: 'Equipment Updated',
        message: `${formData.name} was successfully updated.`,
      });
    } else {
      await equipmentService.add(formData);
      setToast({
        id: Date.now().toString(),
        type: 'success',
        title: 'Equipment Registered',
        message: `${formData.name} was successfully added to the system.`,
      });
    }

    setIsModalOpen(false);
    loadData();
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    await equipmentService.delete(deleteId);
    setToast({
      id: Date.now().toString(),
      type: 'info',
      title: 'Equipment Deleted',
      message: `Equipment record ${deleteId} has been removed.`,
    });
    setDeleteId(null);
    loadData();
  };

  const filteredList = equipmentList.filter((item) => {
    const matchesSearch =
      item.name.toLowerCase().includes(search.toLowerCase()) ||
      item.id.toLowerCase().includes(search.toLowerCase()) ||
      item.manufacturer.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = categoryFilter === 'All' || item.category === categoryFilter;
    const matchesOwnership = ownershipFilter === 'All' || item.ownership === ownershipFilter;
    return matchesSearch && matchesCategory && matchesOwnership;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Equipment Registration"
        description="Register new construction and mining machinery, configure specs, and maintain fleet records."
        action={
          <button
            onClick={handleOpenAddModal}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow-xs transition-colors"
          >
            <Plus className="w-4 h-4" />
            Register Equipment
          </button>
        }
      />

      {/* Filters & Search */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="w-full md:w-80">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search by ID, model or manufacturer..."
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 font-medium">
            <Filter className="w-3.5 h-3.5" /> Filter:
          </div>

          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-800"
          >
            <option value="All">All Categories</option>
            <option value="Excavator">Excavators</option>
            <option value="Dozer">Dozers</option>
            <option value="Wheel Loader">Wheel Loaders</option>
            <option value="Dump Truck">Dump Trucks</option>
            <option value="Compactor">Compactors</option>
            <option value="Motor Grader">Motor Graders</option>
          </select>

          <select
            value={ownershipFilter}
            onChange={(e) => setOwnershipFilter(e.target.value)}
            className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-800"
          >
            <option value="All">All Ownership</option>
            <option value="Rental">Rental</option>
            <option value="Owned">Owned</option>
          </select>
        </div>
      </div>

      {/* Equipment Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-500 uppercase text-[10px] tracking-wider border-b border-gray-200">
              <tr>
                <th className="px-4 py-3.5 font-bold">Equipment ID</th>
                <th className="px-4 py-3.5 font-bold">Equipment Name</th>
                <th className="px-4 py-3.5 font-bold">Category</th>
                <th className="px-4 py-3.5 font-bold">Manufacturer</th>
                <th className="px-4 py-3.5 font-bold">Horse Power</th>
                <th className="px-4 py-3.5 font-bold">Ownership</th>
                <th className="px-4 py-3.5 font-bold">Expected Return</th>
                <th className="px-4 py-3.5 font-bold">Current Status</th>
                <th className="px-4 py-3.5 font-bold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr>
                  <td colSpan={9} className="p-8 text-center text-gray-500">
                    Loading registered equipment records...
                  </td>
                </tr>
              ) : filteredList.length === 0 ? (
                <tr>
                  <td colSpan={9} className="p-12 text-center text-gray-500">
                    <Truck className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                    No equipment records match your current filters.
                  </td>
                </tr>
              ) : (
                filteredList.map((eq) => (
                  <tr key={eq.id} className="hover:bg-gray-50/80 transition-colors">
                    <td className="px-4 py-3.5 font-mono font-semibold text-blue-600">{eq.id}</td>
                    <td className="px-4 py-3.5 font-bold text-gray-900">{eq.name}</td>
                    <td className="px-4 py-3.5 text-gray-600 font-medium">{eq.category}</td>
                    <td className="px-4 py-3.5 text-gray-700">{eq.manufacturer}</td>
                    <td className="px-4 py-3.5 font-medium text-gray-900">{eq.horsePower} HP</td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-md text-[10px] font-semibold border ${
                          eq.ownership === 'Rental'
                            ? 'bg-amber-50 text-amber-700 border-amber-200'
                            : 'bg-blue-50 text-blue-700 border-blue-200'
                        }`}
                      >
                        {eq.ownership}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-gray-600">{eq.expectedReturnDate}</td>
                    <td className="px-4 py-3.5">
                      <StatusBadge status={eq.currentStatus} />
                    </td>
                    <td className="px-4 py-3.5 text-right space-x-1">
                      <button
                        onClick={() => handleOpenEditModal(eq)}
                        className="p-1.5 text-gray-500 hover:text-blue-600 rounded-md hover:bg-gray-100 transition-colors"
                        title="Edit Equipment"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setDeleteId(eq.id)}
                        className="p-1.5 text-gray-500 hover:text-red-600 rounded-md hover:bg-gray-100 transition-colors"
                        title="Delete Equipment"
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

      {/* Add / Edit Equipment Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingEquipment ? 'Edit Equipment Record' : 'Register New Equipment'}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Equipment ID</label>
              <input
                type="text"
                required
                value={formData.id}
                onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Equipment Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Cat 320 Hydraulic Excavator"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Category</label>
              <select
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value as CategoryType })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
              >
                <option value="Excavator">Excavator</option>
                <option value="Dozer">Dozer</option>
                <option value="Wheel Loader">Wheel Loader</option>
                <option value="Dump Truck">Dump Truck</option>
                <option value="Compactor">Compactor</option>
                <option value="Motor Grader">Motor Grader</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Manufacturer</label>
              <input
                type="text"
                required
                value={formData.manufacturer}
                onChange={(e) => setFormData({ ...formData, manufacturer: e.target.value })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Horse Power (HP)</label>
              <input
                type="number"
                required
                min={20}
                max={2000}
                value={formData.horsePower}
                onChange={(e) => setFormData({ ...formData, horsePower: Number(e.target.value) })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Rental or Owned</label>
              <select
                value={formData.ownership}
                onChange={(e) => setFormData({ ...formData, ownership: e.target.value as OwnershipType })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
              >
                <option value="Rental">Rental</option>
                <option value="Owned">Owned</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Expected Return Date</label>
              <input
                type="date"
                required
                value={formData.expectedReturnDate === 'N/A' ? '' : formData.expectedReturnDate}
                onChange={(e) => setFormData({ ...formData, expectedReturnDate: e.target.value || 'N/A' })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Current Status</label>
              <select
                value={formData.currentStatus}
                onChange={(e) => setFormData({ ...formData, currentStatus: e.target.value as EquipmentStatus })}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-900 bg-white"
              >
                <option value="Active">Active</option>
                <option value="Idle">Idle</option>
                <option value="Maintenance">Maintenance</option>
                <option value="Returned">Returned</option>
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
              {editingEquipment ? 'Save Changes' : 'Register Equipment'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={deleteId !== null}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="Delete Equipment Record"
        message={`Are you sure you want to delete equipment ${deleteId}? This will remove telematics and assignment records.`}
      />

      {/* Toast Feedback */}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
};
