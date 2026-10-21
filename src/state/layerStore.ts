import { create } from 'zustand';
import {
  LAYERS,
  LAYER_IDS,
  clampOpacity,
  type BaseMode,
  type LayerId,
} from '../map/layerRegistry';

export interface LayerState {
  visible: Record<LayerId, boolean>;
  opacity: Record<LayerId, number>;
  baseMode: BaseMode;
  toggle: (id: LayerId) => void;
  setVisible: (id: LayerId, visible: boolean) => void;
  setOpacity: (id: LayerId, opacity: number) => void;
  setBaseMode: (mode: BaseMode) => void;
  reset: () => void;
}

function initialVisible(): Record<LayerId, boolean> {
  return Object.fromEntries(LAYERS.map((layer) => [layer.id, layer.defaultVisible])) as Record<
    LayerId,
    boolean
  >;
}

function initialOpacity(): Record<LayerId, number> {
  return Object.fromEntries(LAYERS.map((layer) => [layer.id, layer.defaultOpacity])) as Record<
    LayerId,
    number
  >;
}

export const useLayerStore = create<LayerState>((set, get) => ({
  visible: initialVisible(),
  opacity: initialOpacity(),
  baseMode: 'imagery',

  toggle: (id) => {
    if (!LAYER_IDS.includes(id)) return;
    set((state) => ({ visible: { ...state.visible, [id]: !state.visible[id] } }));
  },

  setVisible: (id, visible) => {
    if (!LAYER_IDS.includes(id) || get().visible[id] === visible) return;
    set((state) => ({ visible: { ...state.visible, [id]: visible } }));
  },

  setOpacity: (id, opacity) => {
    if (!LAYER_IDS.includes(id)) return;
    const next = clampOpacity(opacity);
    if (get().opacity[id] === next) return;
    set((state) => ({ opacity: { ...state.opacity, [id]: next } }));
  },

  setBaseMode: (mode) => {
    if (mode !== 'imagery' && mode !== 'hillshade') return;
    if (get().baseMode === mode) return;
    set({ baseMode: mode });
  },

  reset: () => set({ visible: initialVisible(), opacity: initialOpacity(), baseMode: 'imagery' }),
}));
