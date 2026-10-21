import { useEffect, useRef, useState } from 'react';
import uPlot from 'uplot';
import { formatStepCode } from '../data/format';
import { useTimelineStore } from '../state/timelineStore';
import styles from '../timeline/timeline.module.css';

export interface TelemetryChartProps {
  xs: number[];
  values: number[];
  step: number;
  color: string;
  label: string;
  unit: string;
  formatValue: (value: number) => string;
  fill?: boolean;
  showXLabels?: boolean;
  syncKey: string;
  threshold?: number;
  thresholdLabel?: string;
  height?: number;
}

const DEFAULT_HEIGHT = 62;

export function TelemetryChart({
  xs,
  values,
  step,
  color,
  label,
  unit,
  formatValue,
  fill = false,
  showXLabels = false,
  syncKey,
  threshold,
  thresholdLabel,
  height = DEFAULT_HEIGHT,
}: TelemetryChartProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<uPlot | null>(null);
  const stepRef = useRef(step);
  const updatePlayheadRef = useRef<() => void>(() => undefined);
  const [playheadPercent, setPlayheadPercent] = useState(0);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const maxY = Math.max(...values, threshold ?? 0, 1);
    const labels = xs.map((value) => formatStepCode(value));

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
        width: Math.max(260, host.clientWidth),
        height,
        padding: [4, 4, 0, 0],
        legend: { show: false },
        cursor: {
          show: true,
          x: true,
          y: false,
          drag: { x: false, y: false },
          points: { show: false },
          sync: { key: syncKey, setSeries: false, scales: ['x', null] },
        },
        hooks: {
          draw: [
            (self) => {
              if (threshold === undefined) return;
              const y = self.valToPos(threshold, 'y');
              if (!Number.isFinite(y)) return;
              const { ctx } = self;
              ctx.save();
              ctx.strokeStyle = 'rgba(242, 184, 75, 0.55)';
              ctx.lineWidth = 1;
              ctx.setLineDash([3, 3]);
              ctx.beginPath();
              ctx.moveTo(self.bbox.left, y);
              ctx.lineTo(self.bbox.left + self.bbox.width, y);
              ctx.stroke();
              ctx.restore();
            },
          ],
        },
        scales: {
          x: { time: false, range: [0, Math.max(1, xs.length - 1)] },
          y: { range: [0, Math.ceil(maxY * 1.12)] },
        },
        axes: [
          {
            stroke: '#6f8893',
            font: '8px ui-monospace, "Cascadia Mono", Consolas, monospace',
            ticks: { show: true, stroke: '#27414c', width: 1, size: 3 },
            grid: { show: false },
            size: 15,
            values: (_u, splits) =>
              splits.map((value) => {
                const index = Math.round(value);
                if (!showXLabels || index < 0 || index >= xs.length || Math.abs(value - index) > 0.01) {
                  return '';
                }
                return labels[index] ?? '';
              }),
          },
          {
            stroke: '#6f8893',
            font: '8px ui-monospace, "Cascadia Mono", Consolas, monospace',
            ticks: { show: false },
            grid: { stroke: '#1e3440', width: 1 },
            size: 42,
            values: (_u, splits) =>
              splits.map((value) => (maxY >= 1000 ? String(Math.round(value)) : formatValue(value))),
          },
        ],
        series: [
          {},
          {
            label,
            stroke: color,
            width: 1.6,
            points: { show: false },
            fill: fill
              ? (self: uPlot) => {
                  const gradient = self.ctx.createLinearGradient(
                    0,
                    self.bbox.top,
                    0,
                    self.bbox.top + self.bbox.height,
                  );
                  gradient.addColorStop(0, withAlpha(color, 0.34));
                  gradient.addColorStop(1, withAlpha(color, 0.02));
                  return gradient;
                }
              : undefined,
          },
        ],
      },
      [xs, values],
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
      plot.setSize({ width: Math.floor(width), height });
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
  }, [color, fill, formatValue, height, label, showXLabels, syncKey, threshold, values, xs]);

  useEffect(() => {
    stepRef.current = step;
    updatePlayheadRef.current();
  }, [step]);

  return (
    <div className={styles.chartStack}>
      <div ref={hostRef} className={styles.chartHost} aria-hidden="true" />
      {threshold !== undefined ? (
        <span className={styles.thresholdKey} aria-hidden="true">
          {thresholdLabel ?? `threshold ${formatValue(threshold)} ${unit}`}
        </span>
      ) : null}
      <div className={styles.playhead} style={{ left: `${playheadPercent}%` }} aria-hidden="true" />
    </div>
  );
}

function withAlpha(hex: string, alpha: number): string {
  const value = hex.replace('#', '');
  const red = parseInt(value.slice(0, 2), 16);
  const green = parseInt(value.slice(2, 4), 16);
  const blue = parseInt(value.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}
