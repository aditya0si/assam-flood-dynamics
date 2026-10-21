import { useMemo } from 'react';
import type { FloodSummary, MonsoonSeries } from '../data/schemas';
import { badgeFor } from '../data/labels';
import {
  formatArea,
  formatMmDay,
  formatStage,
  formatStepCode,
} from '../data/format';
import { useTimelineStore } from '../state/timelineStore';
import { DepthDecileStrip } from './DepthDecileStrip';
import { TelemetryChart } from './TelemetryChart';
import styles from '../timeline/timeline.module.css';

interface ChartGridProps {
  summary: FloodSummary;
  series: MonsoonSeries;
}

const SYNC_KEY = 'baanh-telemetry';

interface ChartModel {
  id: string;
  label: string;
  unit: string;
  color: string;
  values: number[];
  formatValue: (value: number) => string;
  className: string;
  fill: boolean;
  threshold?: number;
  thresholdLabel?: string;
}

export function ChartGrid({ summary, series }: ChartGridProps) {
  const step = useTimelineStore((state) => state.step);
  const current = summary.steps[step] ?? summary.steps[0];
  const xs = useMemo(() => summary.steps.map((entry) => entry.step), [summary]);

  const rainfall = series.series.find((entry) => entry.id === 'rainfall');
  const models = useMemo<ChartModel[]>(() => {
    const rainfallByStep = new Map(
      (rainfall?.points ?? []).map((point) => [point.step, point.value]),
    );
    return [
      {
        id: 'area',
        label: 'Inundated area',
        unit: 'km²',
        color: '#7cc7e8',
        values: summary.steps.map((entry) => entry.inundated_area_km2),
        formatValue: formatArea,
        className: summary.class,
        fill: true,
      },
      {
        id: 'stage',
        label: 'Scenario stage above local drainage',
        unit: 'm',
        color: '#f2b84b',
        values: summary.steps.map((entry) => entry.stage_m),
        formatValue: formatStage,
        className: summary.class,
        fill: false,
        threshold: series.threshold.value,
        thresholdLabel: `threshold ${formatStage(series.threshold.value)} m`,
      },
      {
        id: 'rainfall',
        label: rainfall?.label ?? 'Rainfall (synthetic)',
        unit: rainfall?.unit ?? 'mm/day',
        color: '#7fd4b0',
        values: xs.map((stepIndex) => rainfallByStep.get(stepIndex) ?? 0),
        formatValue: formatMmDay,
        className: rainfall?.class ?? 'synthetic',
        fill: true,
      },
    ];
  }, [rainfall, series.threshold.value, summary, xs]);

  const currentRainfall =
    rainfall?.points.find((point) => point.step === step)?.value ?? current.rainfall_mm_day;
  const currentValues: Record<string, string> = {
    area: `${formatArea(current.inundated_area_km2)} km²`,
    stage: `${formatStage(current.stage_m)} m`,
    rainfall: `${formatMmDay(currentRainfall)} mm/day`,
  };

  return (
    <div className={styles.chartGrid} aria-label="Three synced scenario charts">
      <div className={styles.seriesLegend}>
        {models.map((model) => (
          <span key={model.id} className={styles.seriesKey} data-series-id={model.id}>
            <i className={styles.seriesSwatch} style={{ background: model.color }} aria-hidden="true" />
            {model.id === 'area' ? 'Area' : model.id === 'stage' ? 'Stage' : 'Rainfall'}
          </span>
        ))}
        <span className={styles.seriesSyncNote}>shared cursor · playhead follows step</span>
      </div>

      <div className={styles.chartList}>
        {models.map((model, index) => (
          <section key={model.id} className={styles.chartRow} data-chart-id={model.id}>
            <div className={styles.chartRowHead}>
              <span className={styles.chartRowTitle}>{model.label}</span>
              <span className={styles.chartRowMeta}>
                <span className={styles.classBadge}>{badgeFor(model.className)}</span>
                <span className={styles.chartRowValue}>{currentValues[model.id]}</span>
                <span className={styles.chartMuted}>{model.unit}</span>
              </span>
            </div>
            <TelemetryChart
              xs={xs}
              values={model.values}
              step={step}
              color={model.color}
              label={model.label}
              unit={model.unit}
              formatValue={model.formatValue}
              fill={model.fill}
              showXLabels={index === models.length - 1}
              syncKey={SYNC_KEY}
              threshold={model.threshold}
              thresholdLabel={model.thresholdLabel}
              height={32}
            />
          </section>
        ))}
      </div>

      <DepthDecileStrip step={current} />

      <table className={styles.srOnly}>
        <caption>Rainfall, scenario stage, inundated area and depth deciles by step</caption>
        <thead>
          <tr>
            <th scope="col">Step</th>
            <th scope="col">Date</th>
            <th scope="col">Rainfall (mm/day)</th>
            <th scope="col">Scenario stage (m)</th>
            <th scope="col">Inundated area (km²)</th>
            <th scope="col">p10 depth (m)</th>
            <th scope="col">p50 depth (m)</th>
            <th scope="col">p95 depth (m)</th>
          </tr>
        </thead>
        <tbody>
          {summary.steps.map((entry) => (
            <tr key={entry.step}>
              <td>{formatStepCode(entry.step)}</td>
              <td>{entry.step_label}</td>
              <td>{formatMmDay(entry.rainfall_mm_day)}</td>
              <td>{formatStage(entry.stage_m)}</td>
              <td>{formatArea(entry.inundated_area_km2)}</td>
              <td>{entry.delay_deciles.p10}</td>
              <td>{entry.delay_deciles.p50}</td>
              <td>{entry.delay_deciles.p95}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
