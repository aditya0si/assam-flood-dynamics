import { create } from 'zustand';
import {
  deriveOverallHealth,
  INITIAL_TILE_HEALTH,
  type TileHealthLevel,
  type TileHealthSnapshot,
} from '../map/tileHealthState';

interface TileHealthState {
  snapshot: TileHealthSnapshot;
  level: TileHealthLevel;
  /** Distinct overall levels observed since the last reset, in order. */
  history: TileHealthLevel[];
  setSnapshot: (snapshot: TileHealthSnapshot) => void;
  reset: () => void;
}

/**
 * One runtime tile-health record for the whole app. The tracker writes it; the
 * map chip, the status bar and the probe hook read it. No component keeps a
 * second copy.
 */
export const useTileHealthStore = create<TileHealthState>((set) => {
  const initialLevel = deriveOverallHealth(INITIAL_TILE_HEALTH);
  return {
    snapshot: INITIAL_TILE_HEALTH,
    level: initialLevel,
    history: [initialLevel],
    setSnapshot: (snapshot) =>
      set((state) => {
        const level = deriveOverallHealth(snapshot);
        const history =
          state.history[state.history.length - 1] === level
            ? state.history
            : [...state.history, level];
        return { snapshot, level, history };
      }),
    reset: () =>
      set({
        snapshot: INITIAL_TILE_HEALTH,
        level: initialLevel,
        history: [initialLevel],
      }),
  };
});
