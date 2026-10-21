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
  steps: z.array(scenarioStepSchema),
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

export type Manifest = z.infer<typeof manifestSchema>;
export type Scenario = z.infer<typeof scenarioSchema>;
export type ScenarioStep = z.infer<typeof scenarioStepSchema>;
export type FloodSummary = z.infer<typeof floodSummarySchema>;
export type SummaryStep = z.infer<typeof summaryStepSchema>;
export type FrameIndex = z.infer<typeof frameIndexSchema>;
export type FrameClass = z.infer<typeof frameClassSchema>;
export type FrameStep = z.infer<typeof frameStepSchema>;
export type FeatureCollection = z.infer<typeof featureCollectionSchema>;
