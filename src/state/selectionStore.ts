import { create } from 'zustand';

interface SelectionState {
  selectedDistrictId: string | null;
  selectDistrict: (districtId: string | null) => void;
  clear: () => void;
}

export const useSelectionStore = create<SelectionState>((set) => ({
  selectedDistrictId: null,
  selectDistrict: (districtId) =>
    set((state) =>
      state.selectedDistrictId === districtId ? state : { selectedDistrictId: districtId },
    ),
  clear: () => set({ selectedDistrictId: null }),
}));
