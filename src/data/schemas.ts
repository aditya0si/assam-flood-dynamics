import { z } from 'zod';

const bboxSchema = z.tuple([z.number(), z.number(), z.number(), z.number()]);

const geojsonSchema = z.object({
  type: z.literal('FeatureCollection'),
  features: z.array(
    z.object({
      type: z.literal('Feature'),
      geometry: z.any(),
      properties: z.any(),
    }),
  ),
});

export const manifestSchema = z.object({
  schema_version: z.string(),
  dataset_version: z.string(),
  app_min_version: z.string(),
  scenario_id: z.string(),
  generated_at: z.string(),
  bbox: bboxSchema,
  step_count: z.number().int().positive(),
  aoi_v2: z.object({
    area_km2: z.number(),
    assam_area_km2: z.number(),
    flood_prone_area_km2: z.number(),
  }),
});

export const scenarioStepSchema = z.object({
  step: z.number().int().nonnegative(),
  label: z.string(),
  day_offset: z.number().int().nonnegative(),
  phase: z.string(),
  rainfall_mm_day: z.number(),
  mainstem_stage_m: z.number(),
  backwater_m: z.number(),
  stage_m: z.number(),
});

export const scenarioSchema = z.object({
  schema_version: z.string(),
  scenario_id: z.string(),
  name: z.string(),
  class: z.string(),
  not_a_forecast: z.boolean(),
  year_label: z.string().nullable(),
  step_count: z.number().int().positive(),
  total_days: z.number().int().positive(),
  peak_step: z.number().int().nonnegative(),
  threshold_stage_m: z.number(),
  grid: z.object({
    crs: z.string(),
    resolution_m: z.number(),
    bbox: bboxSchema,
    nodata: z.number(),
  }),
  model: z.object({
    name: z.string(),
    version: z.string(),
    burn_depth_m: z.number(),
    max_channel_distance_m: z.number(),
    depth_formula: z.string(),
    depth_bias: z.string(),
    min_component_cells: z.number().int().nonnegative(),
    frame_resolution_scale: z.number().int().positive(),
    depth_bands_m: z.array(z.number().nullable()),
    component_filter: z.object({
      method: z.string(),
      min_cells: z.number().int().nonnegative(),
      min_area_km2: z.number(),
      opening: z.string(),
      applied_before_statistics: z.boolean(),
    }),
  }),
  assumptions: z.array(z.string()),
  limitations: z.array(z.string()),
  steps: z.array(scenarioStepSchema),
});

export const depthDecilesSchema = z.object({
  p10: z.number(),
  p25: z.number(),
  p50: z.number(),
  p75: z.number(),
  p90: z.number(),
  p95: z.number(),
});

export const summaryStepSchema = z.object({
  step: z.number().int().nonnegative(),
  step_label: z.string(),
  day_offset: z.number().int().nonnegative(),
  phase: z.string(),
  rainfall_mm_day: z.number(),
  mainstem_stage_m: z.number(),
  backwater_m: z.number(),
  stage_m: z.number(),
  above_threshold: z.boolean(),
  inundated_area_km2: z.number(),
  wet_cells: z.number().int().nonnegative(),
  delay_deciles: depthDecilesSchema,
  max_depth_m: z.number(),
  mean_depth_m: z.number(),
  new_inundation_km2: z.number(),
  receded_area_km2: z.number(),
  median_depth_m: z.number(),
  p95_depth_m: z.number(),
  frame_file: z.string(),
  frame_png_bytes: z.number().int().positive(),
  png_area_km2: z.number(),
  share_of_aoi_v2: z.number(),
  share_of_assam: z.number(),
  share_of_flood_prone_area: z.number(),
});

export const floodSummarySchema = z.object({
  schema_version: z.string(),
  scenario_id: z.string(),
  class: z.string(),
  peak_step: z.number().int().nonnegative(),
  series_class: z.object({
    rainfall: z.string(),
    mainstem_stage: z.string(),
    backwater: z.string(),
    inundated_area: z.string(),
  }),
  steps: z.array(summaryStepSchema),
  totals: z.object({
    max_area_km2: z.number(),
    peak_stage_m: z.number(),
    scenario_days: z.number().int().positive(),
    districts_any_inundation: z.number().int().nonnegative(),
    aoi_v2_area_km2: z.number(),
    assam_area_km2: z.number(),
    flood_prone_area_km2: z.number(),
  }),
});

export const frameClassSchema = z.object({
  id: z.number().int().nonnegative(),
  label: z.string(),
  color: z.string(),
  alpha: z.number(),
  min_m: z.number().nullable(),
  max_m: z.number().nullable(),
});

export const frameStepSchema = z.object({
  id: z.number().int().nonnegative(),
  label: z.string(),
  stage_m: z.number(),
  file: z.string(),
  area_km2: z.number(),
  png_bytes: z.number().int().positive(),
  png_wet_cells: z.number().int().nonnegative(),
  png_area_km2: z.number(),
});

export const frameIndexSchema = z.object({
  schema_version: z.string(),
  dataset_version: z.string(),
  scenario_id: z.string(),
  class: z.string(),
  bbox: bboxSchema,
  width: z.number().int().positive(),
  height: z.number().int().positive(),
  crs: z.string(),
  source_crs: z.string(),
  source_resolution_m: z.number(),
  frame_resolution_m: z.number(),
  frame_scale: z.number().int().positive(),
  classes: z.array(frameClassSchema),
  steps: z.array(frameStepSchema),
});

export const featureCollectionSchema = geojsonSchema;

export const provenanceStageSchema = z.object({
  command: z.string(),
  stage: z.string(),
  version: z.string(),
});

export const provenanceEntrySchema = z.object({
  id: z.string(),
  class: z.string(),
  dataset: z.string(),
  source_name: z.string(),
  source_url: z.string(),
  licence: z.string(),
  notes: z.string(),
  fetched_at: z.string().nullable(),
  output_paths: z.array(z.string()),
  pipeline: z.array(provenanceStageSchema),
});

export const provenanceSchema = z.object({
  schema_version: z.string(),
  dataset_version: z.string(),
  generated_at: z.string(),
  versions: z.record(z.string(), z.string()),
  entries: z.array(provenanceEntrySchema),
});

export const districtRiskEntrySchema = z.object({
  district_id: z.string(),
  name: z.string(),
  area_km2: z.number(),
  peak_flooded_area_km2: z.number(),
  area_share: z.number(),
  mean_duration_days: z.number(),
  p90_peak_depth_m: z.number(),
  /** P0.2: share of the district's cells wet at peak whose depth exceeds 1.5 m. */
  depth_over_1_5m_share: z.number(),
  /** P0.2: median depth over the district's cells wet at peak, in metres. */
  median_depth_m: z.number(),
  risk_score: z.number(),
  risk_class: z.string(),
  /** P1.7: 0–100 severity profile, separate from risk_score (extent score). */
  severity_index: z.number().min(0).max(100),
  /** P1.7: dense rank by severity_index; `rank` remains the extent-led rank. */
  severity_rank: z.number().int().positive(),
  drivers: z.array(z.string()),
  valid_area_share: z.number(),
  class: z.string(),
  rank: z.number().int().positive(),
});

export const districtRiskSchema = z.object({
  schema_version: z.string(),
  scenario_id: z.string(),
  class: z.string(),
  generated_at: z.string(),
  weights_version: z.string(),
  weights: z.object({
    area_share: z.number(),
    duration: z.number(),
  }),
  reference_values: z.object({
    area_share_saturation: z.number(),
    duration_saturation_days: z.number(),
  }),
  /**
   * P1.7: the exact severity formula and the constants that reproduce it.
   * The index is a separate profile; it is never folded into risk_score.
   */
  severity: z.object({
    formula: z.string(),
    z_statistic: z.string(),
    inputs: z.array(z.string()),
    normalisation: z.object({
      method: z.string(),
      min: z.number(),
      max: z.number(),
      n_districts: z.number().int(),
    }),
    z_population: z.record(
      z.string(),
      z.object({
        mean: z.number(),
        std: z.number(),
      }),
    ),
    note: z.string().optional(),
  }),
  /**
   * P0.4: area share per per-cell risk class over all cells wet at the peak
   * step (S07) with valid HAND. The denominator is peak wet area, not
   * district polygon area, so the four shares sum to 1.
   */
  risk_class_area_share: z.object({
    low: z.number(),
    moderate: z.number(),
    high: z.number(),
    very_high: z.number(),
  }),
  districts: z.array(districtRiskEntrySchema),
  counts: z.record(z.string(), z.number()),
});

export const scorecardSensitivitySchema = z.object({
  iou: z.number().min(0).max(1),
  precision: z.number().min(0).max(1),
  recall: z.number().min(0).max(1),
});

export const scorecardPeakSchema = z.object({
  step: z.number().int().min(0).max(11),
  modelled_area_km2: z.number().nonnegative(),
  iou: z.number().min(0).max(1),
  precision: z.number().min(0).max(1),
  recall: z.number().min(0).max(1),
  f1: z.number().min(0).max(1),
  area_bias_pct: z.number(),
});

export const scorecardSceneSchema = z.object({
  scene_id: z.string().min(1),
  datetime: z.string().min(1),
  platform: z.string().min(1),
  relative_orbit: z.number().int(),
  /** REVIEW-17 addition: the Otsu threshold the scene actually chose, in dB. */
  threshold_db: z.number(),
  observed_area_km2: z.number().positive(),
  observed_water_fraction_of_aoi: z.number().min(0).max(1),
  best_match_step: z.number().int().min(0).max(11),
  best_match_iou: z.number().min(0).max(1),
  peak_step: scorecardPeakSchema,
  sensitivity: z.object({
    minus2db: scorecardSensitivitySchema,
    plus2db: scorecardSensitivitySchema,
  }),
});

export const scorecardSchema = z.object({
  schema_version: z.string(),
  generated_at: z.string(),
  method: z.object({
    collection: z.literal('sentinel-1-grd'),
    threshold_method: z.literal('otsu'),
    sensitivity_db: z.tuple([z.literal(-2), z.literal(0), z.literal(2)]),
    slope_mask_deg: z.number(),
    min_component_cells: z.number().int(),
    resampling: z.literal('average→nearest'),
    crs: z.literal('EPSG:32646'),
    resolution_m: z.number(),
  }),
  scenes: z.array(scorecardSceneSchema).length(2),
  summary: z.object({
    mean_iou_over_scenes: z.number().min(0).max(1),
    mean_precision: z.number().min(0).max(1),
    mean_recall: z.number().min(0).max(1),
    worst_scene: z.string().min(1),
    caveats: z.array(z.string()).min(1),
  }),
});

export const seriesPointSchema = z.object({
  step: z.number().int().nonnegative(),
  day: z.number().int().nonnegative(),
  value: z.number(),
});

export const seriesEntrySchema = z.object({
  id: z.string(),
  label: z.string(),
  unit: z.string(),
  class: z.string(),
  source_note: z.string(),
  points: z.array(seriesPointSchema),
});

export const monsoonSeriesSchema = z.object({
  schema_version: z.string(),
  dataset_version: z.string(),
  scenario_id: z.string(),
  class: z.string(),
  series: z.array(seriesEntrySchema),
  threshold: z.object({
    id: z.string(),
    label: z.string(),
    value: z.number(),
    unit: z.string(),
    class: z.string(),
    note: z.string(),
  }),
});

export const riskZoneFeatureCollectionSchema = z.object({
  type: z.literal('FeatureCollection'),
  name: z.string(),
  schema_version: z.string(),
  dataset_version: z.string(),
  class: z.string(),
  features: z.array(
    z.object({
      type: z.literal('Feature'),
      geometry: z.any(),
      properties: z.object({
        zone_id: z.string(),
        risk_class: z.string(),
        risk_score: z.number(),
        mean_hand_m: z.number(),
        mean_duration_days: z.number(),
        peak_depth_m: z.number(),
        area_km2: z.number(),
        class: z.string(),
        model_version: z.string(),
        label: z.string(),
      }),
    }),
  ),
});

export const hotspotFeatureCollectionSchema = z.object({
  type: z.literal('FeatureCollection'),
  name: z.string(),
  schema_version: z.string(),
  dataset_version: z.string(),
  class: z.string(),
  features: z.array(
    z.object({
      type: z.literal('Feature'),
      geometry: z.object({
        type: z.literal('Point'),
        coordinates: z.tuple([z.number(), z.number()]),
      }),
      properties: z.object({
        hotspot_id: z.string(),
        rank: z.number().int().positive(),
        reason: z.string(),
        area_km2: z.number(),
        hand_mean_m: z.number(),
        distance_to_channel_m: z.number(),
        first_step: z.number().int().nonnegative(),
        peak_depth_m: z.number(),
        centroid_lon: z.number(),
        centroid_lat: z.number(),
        district_id: z.string(),
        class: z.string(),
        label: z.string(),
      }),
    }),
  ),
});

export type Manifest = z.infer<typeof manifestSchema>;
export type Scenario = z.infer<typeof scenarioSchema>;
export type ScenarioStep = z.infer<typeof scenarioStepSchema>;
export type FloodSummary = z.infer<typeof floodSummarySchema>;
export type SummaryStep = z.infer<typeof summaryStepSchema>;
export type FrameIndex = z.infer<typeof frameIndexSchema>;
export type FrameClass = z.infer<typeof frameClassSchema>;
export type FrameStep = z.infer<typeof frameStepSchema>;
export type FeatureCollection = z.infer<typeof featureCollectionSchema>;
export type DepthDeciles = z.infer<typeof depthDecilesSchema>;
export type Provenance = z.infer<typeof provenanceSchema>;
export type ProvenanceEntry = z.infer<typeof provenanceEntrySchema>;
export type ProvenanceStage = z.infer<typeof provenanceStageSchema>;
export type DistrictRisk = z.infer<typeof districtRiskSchema>;
export type DistrictRiskEntry = z.infer<typeof districtRiskEntrySchema>;
export type SeverityMethod = DistrictRisk['severity'];
export type Scorecard = z.infer<typeof scorecardSchema>;
export type ScorecardScene = z.infer<typeof scorecardSceneSchema>;
export type ScorecardPeak = z.infer<typeof scorecardPeakSchema>;
export type ScorecardSensitivity = z.infer<typeof scorecardSensitivitySchema>;
export type MonsoonSeries = z.infer<typeof monsoonSeriesSchema>;
export type SeriesEntry = z.infer<typeof seriesEntrySchema>;
export type RiskZoneCollection = z.infer<typeof riskZoneFeatureCollectionSchema>;
export type RiskZoneProperties = RiskZoneCollection['features'][number]['properties'];
export type HotspotCollection = z.infer<typeof hotspotFeatureCollectionSchema>;
export type HotspotProperties = HotspotCollection['features'][number]['properties'];
