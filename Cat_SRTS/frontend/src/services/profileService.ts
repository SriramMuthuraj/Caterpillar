import { CustomerProfile } from '../types';
import { INITIAL_CUSTOMER_PROFILE } from '../mocks/data';
import { delay } from './api';

let currentProfile: CustomerProfile = { ...INITIAL_CUSTOMER_PROFILE };

export const profileService = {
  async getProfile(): Promise<CustomerProfile> {
    await delay();
    return { ...currentProfile };
  },

  async updateProfile(updates: Partial<CustomerProfile>): Promise<CustomerProfile> {
    await delay();
    currentProfile = { ...currentProfile, ...updates };
    return { ...currentProfile };
  },
};
