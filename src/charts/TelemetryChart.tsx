import { useEffect, useRef, useState } from 'react';
import uPlot from 'uplot';
import type { FloodSummary } from '../data/schemas';
import { formatArea, formatStage, formatStepCode } from '../data/format';
import { useTimelineStore } from '../state/timelineStore';
import styles from '../timeline/timeline.module.css';

interface TelemetryChartProps {
  summary: FloodSummary;
}

const CHART_HEIGHT = 126;

export function TelemetryChart({ summary }: TelemetryChartProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<uPlot | null>(null);
  const step = useTimelineStore((state) => state.step);
  const stepRef = useRef(step);
  const updatePlayheadRef = useRef<() => void>(() => undefined);
  const [playheadPercent, setPlayheadPercent] = useState(0);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const xs = summary.steps.map((entry) => entry.step);
    const ys = summary.steps.map((entry) => entry.inundated_area_km2);
    const labels = summary.steps.map((entry) => formatStepCode(entry.step));
    const maxY = Math.max(...ys, 1);

    const makePlayhead = (plot: uPlot) => {
      const x = plot.valToPos(stepRef.current, 'x');
      if (!Number.isFinite(x) || plot.width <= 0) {
        setPlayheadPercent(0);
        return;
      }
      setPlayheadPercent(Math.min(100, Math.max(0, (x / plot.width) * 100)));
    };

    const plot = new uPlot(
      {
        width: Math.max(320, host.clientWidth),
        height: CHART_HEIGHT,
        padding: [10, 8, 0, 0],
        legend: { show: false },
        cursor: {
          show: true,
          x: true,
          y: false,
          drag: { x: false, y: false },
          points: { show: false },
        },
        scales: {
          x: { time: false, range: [0, Math.max(1, xs.length - 1)] },
          y: { range: [0, Math.ceil(maxY * 1.12)] },
        },
        axes: [
          {
            stroke: '#7d95a0',
            font: '10px ui-monospace, "Cascadia Mono", Consolas, monospace',
            ticks: { show: true, stroke: '#27414c', width: 1 },
            grid: { show: false },
            size: 20,
            values: (_u, splits) => splits.map((value) => labels[Math.round(value)] ?? ''),
          },
          {
            stroke: '#7d95a0',
            font: '10px ui-monospace, "Cascadia Mono", Consolas, monospace',
            ticks: { show: false },
            grid: { stroke: '#1e3440', width: 1 },
            size: 52,
            values: (_u, splits) => splits.map((value) => String(Math.round(value))),
          },
        ],
        series: [
          {},
          {
            label: 'Inundated area (km²)',
            stroke: '#7cc7e8',
            width: 1.6,
            points: { show: false },
            fill: (u: uPlot) => {
              const gradient = u.ctx.createLinearGradient(0, u.bbox.top, 0, u.bbox.top + u.bbox.height);
              gradient.addColorStop(0, 'rgba(124, 199, 232, 0.34)');
              gradient.addColorStop(1, 'rgba(124, 199, 232, 0.02)');
              return gradient;
            },
          },
        ],
      },
      [xs, ys],
      host,
    );

    plotRef.current = plot;
    makePlayhead(plot);
    updatePlayheadRef.current = () => makePlayhead(plot);

    const onClick = (event: MouseEvent) => {
      const rect = plot.over.getBoundingClientRect();
      const value = plot.posToVal(event.clientX - rect.left, 'x');
      const index = Math.max(0, Math.min(xs.length - 1, Math.round(value)));
      useTimelineStore.getState().setStep(index, 'user');
    };
    plot.over.addEventListener('click', onClick);

    const resizeObserver = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? host.clientWidth;
      if (width <= 0) return;
      plot.setSize({ width: Math.floor(width), height: CHART_HEIGHT });
      makePlayhead(plot);
    });
    resizeObserver.observe(host);

    return () => {
      resizeObserver.disconnect();
      plot.over.removeEventListener('click', onClick);
      plot.destroy();
      plotRef.current = null;
      updatePlayheadRef.current = () => undefined;
    };
  }, [summary]);

  useEffect(() => {
    stepRef.current = step;
    updatePlayheadRef.current();
  }, [step]);

  const current = summary.steps[step];

  return (
    <figure className={styles.chartFigure}>
      <figcaption className={styles.chartCaption}>
        <span>
          Inundated area <span className={styles.chartMuted}>(scenario)</span>
        </span>
        <span className={styles.chartUnit}>km² · {summary.steps.length}-step series</span>
      </figcaption>

      <div className={styles.chartStack}>
        <div ref={hostRef} className={styles.chartHost} aria-hidden="true" />
        <div
          className={styles.playhead}
          style={{ left: `${playheadPercent}%` }}
          aria-hidden="true"
        />
      </div>

      <div className={styles.chartFooter}>
        <span>
          {current ? `${formatStepCode(step)} · ${current.step_label}` : ''} —{' '}
          {current ? `${formatArea(current.inundated_area_km2)} km²` : ''}
        </span>
        <span className={styles.chartMuted}>click chart to step</span>
      </div>

      <table className={styles.srOnly}>
        <caption>Inundated area and scenario stage by step</caption>
        <thead>
          <tr>
            <th scope="col">Step</th>
            <th scope="col">Date</th>
            <th scope="col">Scenario stage (m)</th>
            <th scope="col">Inundated area (km²)</th>
            <th scope="col">Share of Assam</th>
          </tr>
        </thead>
        <tbody>
          {summary.steps.map((entry) => (
            <tr key={entry.step}>
              <td>{formatStepCode(entry.step)}</td>
              <td>{entry.step_label}</td>
              <td>{formatStage(entry.stage_m)}</td>
              <td>{formatArea(entry.inundated_area_km2)}</td>
              <td>{(entry.share_of_assam * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
