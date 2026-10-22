import { useMemo } from 'react';
import type { FloodSummary, MonsoonSeries, Rainfall, RainfallForecast } from '../data/schemas';
import {
  formatArea,
  formatMmDay,
  formatStage,
  formatStepCode,
} from '../data/format';
import { ClassBadge, DataAge } from '../shell/DataBadge';
import { useTimelineStore } from '../state/timelineStore';
import { TelemetryChart } from './TelemetryChart';
import styles from '../timeline/timeline.module.css';

interface ChartGridProps {
  summary: FloodSummary;
  series: MonsoonSeries;
  rainfall: Rainfall;
  forecast: RainfallForecast;
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
  dataAsOf: string;
  fill: boolean;
  threshold?: number;
  thresholdLabel?: string;
}

function formatMmTotal(value: number): string {
  return `${Math.round(value).toLocaleString('en-IN')} mm`;
}

function RainfallContext({ rainfall, forecast }: { rainfall: Rainfall; forecast: RainfallForecast }) {
  const aoi = rainfall.aoi_monsoon;
  const seasons = aoi.seasons;
  const max = Math.max(...seasons.map((entry) => entry.monsoon_mm), 1);
  const forecastTotal = forecast.forecast_window.points.reduce(
    (sum, point) => sum + point.value,
    0,
  );
  return (
    <section className={styles.rainfallContext} data-rainfall-context="true" aria-label="ERA5 monsoon context">
      <div className={styles.contextHead}>
        <span className={styles.contextTitle}>ERA5 monsoon context</span>
        <span className={styles.contextBadges}>
          <ClassBadge className="reanalysis" />
          <DataAge dataAsOf={rainfall.data_as_of} compact />
        </span>
      </div>
      <div className={styles.contextBody}>
        <span className={styles.contextStat}>
          2022 JJAS <strong>{formatMmTotal(aoi.monsoon_2022_mm)}</strong>
        </span>
        <span className={styles.contextStat}>
          2015-2025 mean <strong>{formatMmTotal(aoi.monsoon_2015_2025_mean_mm)}</strong>
        </span>
        <span
          className={
            aoi.anomaly_2022_vs_mean_mm >= 0 ? styles.contextPositive : styles.contextNegative
          }
        >
          {aoi.anomaly_2022_vs_mean_mm >= 0 ? '+' : ''}
          {Math.round(aoi.anomaly_2022_vs_mean_mm).toLocaleString('en-IN')} mm vs mean
        </span>
      </div>
      <div className={styles.seasonBars} aria-label="ERA5 JJAS totals by year">
        {seasons.map((entry) => (
          <span
            key={entry.year}
            className={`${styles.seasonBarCell} ${entry.year === 2022 ? styles.seasonBarPeak : ''}`}
            data-season-year={entry.year}
            title={`${entry.year} JJAS ${Math.round(entry.monsoon_mm).toLocaleString('en-IN')} mm`}
          >
            <i style={{ height: `${Math.max(3, Math.round((entry.monsoon_mm / max) * 100))}%` }} />
            <em>{entry.year === 2022 ? '’22' : String(entry.year).slice(2)}</em>
          </span>
        ))}
      </div>
      <div className={styles.forecastLine} data-forecast-window="true">
        <span>Open-Meteo current window (model, not observed)</span>
        <ClassBadge className={forecast.forecast_window.class} />
        <DataAge dataAsOf={forecast.data_as_of} compact />
        <span className={styles.contextStat}>{formatMmTotal(forecastTotal)}</span>
      </div>
      <p className={styles.contextCaveat}>
        ERA5 is model-based reanalysis, not an observation; it is biased in complex terrain.
      </p>
    </section>
  );
}

export function ChartGrid({ summary, series, rainfall, forecast }: ChartGridProps) {
  const step = useTimelineStore((state) => state.step);
  const current = summary.steps[step] ?? summary.steps[0];
  const xs = useMemo(() => summary.steps.map((entry) => entry.step), [summary]);

  const rainfallSeries = series.series.find((entry) => entry.id === 'rainfall');
  const models = useMemo<ChartModel[]>(() => {
    const rainfallByStep = new Map(
      (rainfallSeries?.points ?? []).map((point) => [point.step, point.value]),
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
        dataAsOf: summary.data_as_of,
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
        dataAsOf: summary.data_as_of,
        fill: false,
        threshold: series.threshold.value,
        thresholdLabel: `threshold ${formatStage(series.threshold.value)} m`,
      },
      {
        id: 'rainfall',
        label: rainfallSeries?.label ?? 'Rainfall (scenario)',
        unit: rainfallSeries?.unit ?? 'mm/day',
        color: '#7fd4b0',
        values: xs.map((stepIndex) => rainfallByStep.get(stepIndex) ?? 0),
        formatValue: formatMmDay,
        className: rainfallSeries?.class ?? 'scenario',
        dataAsOf: rainfallSeries?.data_as_of ?? summary.data_as_of,
        fill: true,
      },
    ];
  }, [rainfallSeries, series.threshold.value, summary, xs]);

  const currentRainfall =
    rainfallSeries?.points.find((point) => point.step === step)?.value ?? current.rainfall_mm_day;
  // Units are rendered once, by the chartMuted span; formatting only the number
  // here avoids labels such as "10010.6 km² km²".
  const currentValues: Record<string, string> = {
    area: formatArea(current.inundated_area_km2),
    stage: formatStage(current.stage_m),
    rainfall: formatMmDay(currentRainfall),
  };

  return (
    <div className={styles.chartGrid} aria-label="Three synced scenario charts" data-rainfall-chart="true">
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
                <ClassBadge className={model.className} />
                <DataAge dataAsOf={model.dataAsOf} compact />
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
              height={34}
            />
          </section>
        ))}
      </div>

      <RainfallContext rainfall={rainfall} forecast={forecast} />

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
