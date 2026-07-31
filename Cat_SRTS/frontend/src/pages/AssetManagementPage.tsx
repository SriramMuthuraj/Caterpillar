import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  Boxes,
  Eye,
  Edit2,
  Filter,
  CheckCircle2,
  Calendar,
  User,
  ShieldAlert,
  HardDrive,
  Flame,
  ArrowUpRight,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { SearchInput } from '../components/ui/SearchInput';
import { StatusBadge } from '../components/ui/StatusBadge';
import { Modal } from '../components/ui/Modal';
import { assetService } from '../services/assetService';
import { equipmentService } from '../services/equipmentService';
import { Equipment } from '../types';
import { formatCurrency } from '../utils/formatters';

export const AssetManagementPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || '';

  const [assets, setAssets] = useState<Equipment[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(initialQuery);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [selectedStatus, setSelectedStatus] = useState('All');
  const [selectedOwnership, setSelectedOwnership] = useState('All');

  // Asset Details Modal
  const [viewAsset, setViewAsset] = useState<Equipment | null>(null);

  const fetchAssets = async () => {
    setLoading(true);
    const data = await assetService.getAssets(search, selectedCategory, selectedStatus, selectedOwnership);
    setAssets(data);
    setLoading(false);
  };

  useEffect(() => {
    fetchAssets();
  }, [search, selectedCategory, selectedStatus, selectedOwnership]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Asset Management Directory"
        description="Searchable enterprise inventory of all owned machinery and active Caterpillar equipment rentals."
        action={
          <div className="text-xs font-semibold px-3 py-1.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg">
            Total Assets: {assets.length} Units
          </div>
        }
      />

      {/* Filter Controls */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="w-full md:w-80">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search Equipment ID, name, operator..."
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 font-medium">
            <Filter className="w-3.5 h-3.5" /> Filters:
          </div>

          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
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
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-800"
          >
            <option value="All">All Statuses</option>
            <option value="Active">Active</option>
            <option value="Idle">Idle</option>
            <option value="Maintenance">Maintenance</option>
            <option value="Returned">Returned</option>
          </select>

          <select
            value={selectedOwnership}
            onChange={(e) => setSelectedOwnership(e.target.value)}
            className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-gray-800"
          >
            <option value="All">All Ownership</option>
            <option value="Rental">Rental</option>
            <option value="Owned">Owned</option>
          </select>
        </div>
      </div>

      {/* Assets Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-500 uppercase text-[10px] tracking-wider border-b border-gray-200">
              <tr>
                <th className="px-4 py-3.5 font-bold">Equipment ID</th>
                <th className="px-4 py-3.5 font-bold">Equipment Name</th>
                <th className="px-4 py-3.5 font-bold">Status</th>
                <th className="px-4 py-3.5 font-bold">Ownership</th>
                <th className="px-4 py-3.5 font-bold">Return Date</th>
                <th className="px-4 py-3.5 font-bold">Assigned Operator</th>
                <th className="px-4 py-3.5 font-bold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-gray-500">
                    Loading asset inventory records...
                  </td>
                </tr>
              ) : assets.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-12 text-center text-gray-500">
                    <Boxes className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                    No assets found for your search criteria.
                  </td>
                </tr>
              ) : (
                assets.map((asset) => (
                  <tr key={asset.id} className="hover:bg-gray-50/80 transition-colors">
                    <td className="px-4 py-3.5 font-mono font-semibold text-blue-600">{asset.id}</td>
                    <td className="px-4 py-3.5 font-bold text-gray-900">
                      <div>{asset.name}</div>
                      <div className="text-[10px] text-gray-400 font-normal">{asset.category} • {asset.manufacturer}</div>
                    </td>
                    <td className="px-4 py-3.5">
                      <StatusBadge status={asset.currentStatus} />
                    </td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-md text-[10px] font-semibold border ${
                          asset.ownership === 'Rental'
                            ? 'bg-amber-50 text-amber-700 border-amber-200'
                            : 'bg-blue-50 text-blue-700 border-blue-200'
                        }`}
                      >
                        {asset.ownership}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 font-mono text-gray-600">
                      <div className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-gray-400" />
                        {asset.expectedReturnDate}
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-1.5 font-medium text-gray-900">
                        <User className="w-3.5 h-3.5 text-gray-400" />
                        {asset.assignedOperatorName || <span className="text-gray-400 italic font-normal">Unassigned</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-right space-x-1">
                      <button
                        onClick={() => setViewAsset(asset)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-md transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" /> View
                      </button>
                      <Link
                        to="/registration/equipment"
                        className="p-1.5 inline-block text-gray-500 hover:text-blue-600 rounded-md hover:bg-gray-100 transition-colors"
                        title="Edit Asset"
                      >
                        <Edit2 className="w-4 h-4" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Asset Specifications Detail Modal */}
      {viewAsset && (
        <Modal
          isOpen={viewAsset !== null}
          onClose={() => setViewAsset(null)}
          title={`Asset Specifications: ${viewAsset.id}`}
          maxWidth="lg"
        >
          <div className="space-y-4 text-xs">
            <div className="p-4 bg-gray-50 rounded-xl border border-gray-200 flex items-start justify-between">
              <div>
                <h4 className="text-base font-bold text-gray-900">{viewAsset.name}</h4>
                <p className="text-xs text-gray-500 mt-0.5">
                  {viewAsset.manufacturer} • {viewAsset.category} • {viewAsset.horsePower} HP
                </p>
              </div>
              <StatusBadge status={viewAsset.currentStatus} size="md" />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div className="p-3 bg-white border border-gray-200 rounded-lg">
                <span className="text-[10px] text-gray-400 font-semibold uppercase">Serial Number</span>
                <p className="font-mono font-bold text-gray-900 mt-1">{viewAsset.serialNumber || 'CAT-N/A'}</p>
              </div>
              <div className="p-3 bg-white border border-gray-200 rounded-lg">
                <span className="text-[10px] text-gray-400 font-semibold uppercase">Ownership</span>
                <p className="font-bold text-gray-900 mt-1">{viewAsset.ownership}</p>
              </div>
              <div className="p-3 bg-white border border-gray-200 rounded-lg">
                <span className="text-[10px] text-gray-400 font-semibold uppercase">Daily Rental Rate</span>
                <p className="font-bold text-blue-600 mt-1">
                  {viewAsset.dailyRate ? formatCurrency(viewAsset.dailyRate) + ' / day' : 'Owned Unit'}
                </p>
              </div>
              <div className="p-3 bg-white border border-gray-200 rounded-lg">
                <span className="text-[10px] text-gray-400 font-semibold uppercase">Assigned Operator</span>
                <p className="font-bold text-gray-900 mt-1">{viewAsset.assignedOperatorName || 'Unassigned'}</p>
              </div>
              <div className="p-3 bg-white border border-gray-200 rounded-lg">
                <span className="text-[10px] text-gray-400 font-semibold uppercase">Assigned Site</span>
                <p className="font-bold text-gray-900 mt-1">{viewAsset.assignedSite || 'Central Yard'}</p>
              </div>
              <div className="p-3 bg-white border border-gray-200 rounded-lg">
                <span className="text-[10px] text-gray-400 font-semibold uppercase">Return Date</span>
                <p className="font-bold text-gray-900 mt-1">{viewAsset.expectedReturnDate}</p>
              </div>
            </div>

            <div className="p-3 bg-blue-50/60 rounded-xl border border-blue-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-blue-600" />
                <span className="font-semibold text-gray-900">CAT Product Link™ Telematics Status</span>
              </div>
              <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded">
                Connected
              </span>
            </div>

            <div className="pt-3 border-t border-gray-100 flex items-center justify-end gap-2">
              <Link
                to="/usage"
                onClick={() => setViewAsset(null)}
                className="px-3.5 py-2 text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100"
              >
                View Telematics Usage
              </Link>
              <button
                type="button"
                onClick={() => setViewAsset(null)}
                className="px-3.5 py-2 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700"
              >
                Close Details
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
