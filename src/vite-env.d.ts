/// <reference types="vite/client" />

interface BaanhProbe {
  readonly step: number;
  readonly frameFile: string;
  readonly isPlaying: boolean;
  readonly tileHealth: 'live' | 'degraded' | 'offline';
}

interface Window {
  /** Read-only runtime probe installed by the map (R4). */
  readonly __baanh?: BaanhProbe;
}
