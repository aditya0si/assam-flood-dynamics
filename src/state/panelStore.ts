import { create } from 'zustand';

export type PanelId = 'risk' | 'validation' | 'provenance' | 'methodology' | 'layers';

export const PANEL_ORDER: PanelId[] = ['risk', 'validation', 'provenance', 'methodology', 'layers'];

export const PANEL_LABELS: Record<PanelId, string> = {
  risk: 'Risk',
  validation: 'Validation',
  provenance: 'Provenance',
  methodology: 'Methodology',
  layers: 'Layers',
};

interface PanelState {
  activePanel: PanelId;
  open: (panel: PanelId) => void;
  reset: () => void;
}

export const DEFAULT_PANEL: PanelId = 'risk';

export const usePanelStore = create<PanelState>((set) => ({
  activePanel: DEFAULT_PANEL,
  open: (panel) => {
    if (!PANEL_ORDER.includes(panel)) return;
    set({ activePanel: panel });
  },
  reset: () => set({ activePanel: DEFAULT_PANEL }),
}));
