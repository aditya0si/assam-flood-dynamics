/// <reference types="vite/client" />

interface BaanhLayersProbe {
  readonly visible: string[];
  readonly opacity: Record<string, number>;
  readonly baseMode: 'imagery' | 'hillshade';
}

interface BaanhTopDistrictProbe {
  readonly name: string;
  /** Rounded display score, exactly what the rail top row shows. */
  readonly score: number;
  /** Raw committed risk_score. */
  readonly riskScore: number;
  readonly scoreLabel: string;
  readonly riskClass: string;
  readonly rank: number;
  readonly districtId: string;
  readonly areaShare: number;
  readonly durationDays: number;
  readonly peakDepthM: number;
  toString: () => string;
}

interface BaanhProbe {
  readonly step: number;
  readonly frameFile: string;
  readonly isPlaying: boolean;
  readonly tileHealth: 'live' | 'degraded' | 'offline';
  /** Active rail panel id: risk | provenance | methodology | layers. */
  readonly panel: string;
  /** Visible layer ids, opacity per layer, and the active base mode. */
  readonly layers: BaanhLayersProbe;
  /** The top row of district-risk.json, or null if the ranking is empty. */
  readonly districtTop: BaanhTopDistrictProbe | null;
}

interface Window {
  /** Read-only runtime probe installed by the map (R4/B2). */
  readonly __baanh?: BaanhProbe;
}
