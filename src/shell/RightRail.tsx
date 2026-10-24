import { useState, type KeyboardEvent } from 'react';
import type { Dataset } from '../data/types';

import { formatStepCode } from '../data/format';
import { useTimelineStore } from '../state/timelineStore';
import { PANEL_LABELS, PANEL_ORDER, usePanelStore, type PanelId } from '../state/panelStore';
import { PanelRouter } from './PanelRouter';
import { ClassBadge } from './DataBadge';
import styles from '../panels/panels.module.css';

interface RightRailProps {
  dataset: Dataset;
}

export function RightRail({ dataset }: RightRailProps) {
  const [size, setSize] = useState<'collapsed' | 'default' | 'expanded'>('default');
  const activePanel = usePanelStore((state) => state.activePanel);
  const open = usePanelStore((state) => state.open);
  const step = useTimelineStore((state) => state.step);
  const current = dataset.summary.steps[step] ?? dataset.summary.steps[0];

  const onTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, panel: PanelId) => {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft' && event.key !== 'Home' && event.key !== 'End') {
      return;
    }
    event.preventDefault();
    const index = PANEL_ORDER.indexOf(panel);
    let next = index;
    if (event.key === 'ArrowRight') next = (index + 1) % PANEL_ORDER.length;
    if (event.key === 'ArrowLeft') next = (index - 1 + PANEL_ORDER.length) % PANEL_ORDER.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = PANEL_ORDER.length - 1;
    const nextPanel = PANEL_ORDER[next];
    open(nextPanel);
    const target = document.getElementById(`panel-tab-${nextPanel}`);
    target?.focus();
  };

  // ESC is the way back out of the panel body: focus returns to the tab that
  // owns the panel, so keyboard users never lose their place in the rail.
  const onRailKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    // The analysis skip link lands directly before its active tab. Rail sizing
    // remains reachable in normal tab order and with Shift+Tab from that tab.
    if (event.key === 'Tab' && !event.shiftKey && event.target === event.currentTarget && size !== 'collapsed') {
      event.preventDefault();
      document.getElementById(`panel-tab-${activePanel}`)?.focus();
      return;
    }
    if (event.key !== 'Escape') return;
    const target = event.target;
    if (!(target instanceof HTMLElement) || !target.closest('[role="tabpanel"]')) return;
    event.preventDefault();
    document.getElementById(`panel-tab-${activePanel}`)?.focus();
  };

  return (
    <aside
      id="analysis-rail"
      className={styles.rail}
      aria-label="Analysis rail"
      tabIndex={-1}
      data-active-panel={activePanel}
      data-rail-size={size}
      onKeyDown={onRailKeyDown}
    >
      <header className={styles.railHead}>
        <div className={styles.railTitleBlock}>
          <span className={styles.railKicker}>Analysis rail</span>
          <span className={styles.railScenario}>
            {formatStepCode(step)} · {current.step_label}
          </span>
        </div>
        <div className={styles.railControls}>
          <button type="button" aria-label={size === 'collapsed' ? 'Show analysis' : 'Hide analysis'} aria-expanded={size !== 'collapsed'} aria-controls="analysis-content" onClick={() => setSize(size === 'collapsed' ? 'default' : 'collapsed')}>
            {size === 'collapsed' ? '‹' : '›'}
          </button>
          {size !== 'collapsed' && <button type="button" aria-label={size === 'expanded' ? 'Default analysis width' : 'Expand analysis width'} aria-pressed={size === 'expanded'} onClick={() => setSize(size === 'expanded' ? 'default' : 'expanded')}>↔</button>}
        </div>
      </header>

      <div id="analysis-content" className={styles.railContent} hidden={size === 'collapsed'}>
      <div className={styles.tabList} role="tablist" aria-label="Analysis panels">
        {PANEL_ORDER.map((panel) => (
          <button
            key={panel}
            id={`panel-tab-${panel}`}
            type="button"
            role="tab"
            className={`${styles.tab} ${activePanel === panel ? styles.tabActive : ''}`}
            aria-label={PANEL_LABELS[panel]}
            aria-selected={activePanel === panel}
            aria-controls={`panel-${panel}`}
            tabIndex={activePanel === panel ? 0 : -1}
            onClick={() => open(panel)}
            onKeyDown={(event) => onTabKeyDown(event, panel)}
            data-panel-tab={panel}
          >
            {PANEL_LABELS[panel]}
            {panel === 'validation' && <ClassBadge className="observed" />}
          </button>
        ))}
      </div>

      <PanelRouter dataset={dataset} />
      </div>
    </aside>
  );
}
