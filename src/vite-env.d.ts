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
  readonly centroidLon: number | null;
  readonly centroidLat: number | null;
  toString: () => string;
}

interface BaanhCameraProbe {
  readonly center: [number, number];
  readonly zoom: number;
  readonly pitch: number;
}

interface BaanhTileSourcesProbe {
  readonly dem: 'loading' | 'live' | 'degraded' | 'offline';
  readonly imagery: 'loading' | 'live' | 'degraded' | 'offline';
}

interface BaanhProbe {
  readonly step: number;
  readonly frameFile: string;
  readonly isPlaying: boolean;
  /** Painted map frames since mount; advances on every MapLibre 'render'. */
  readonly renderSeq: number;
  /** True once the style document and required layers/sources are installed. */
  readonly styleLoaded: boolean;
  /** Request one painted frame without changing camera, layers or sources. */
  requestRender(): void;
  readonly tileHealth: 'live' | 'degraded' | 'offline';
  /** Per-host state behind the aggregate level, for diagnosing partial blocks. */
  readonly tileSources: BaanhTileSourcesProbe;
  /** Every distinct overall level observed since the map mounted, in order. */
  readonly tileHealthHistory: string[];
  /** Live MapLibre camera: centre, zoom and pitch (B5 hero reach). */
  readonly camera: BaanhCameraProbe | null;
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
