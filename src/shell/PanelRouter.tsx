import { useEffect, useRef } from 'react';
import type { Dataset } from '../data/types';
import { MethodologyPanel } from '../panels/MethodologyPanel';
import { LayersPanel } from '../panels/LayersPanel';
import { ProvenancePanel } from '../panels/ProvenancePanel';
import { RiskPanel } from '../panels/RiskPanel';
import { ValidationPanel } from '../panels/ValidationPanel';
import { usePanelStore } from '../state/panelStore';
import styles from '../panels/panels.module.css';

interface PanelRouterProps {
  dataset: Dataset;
}

export function PanelRouter({ dataset }: PanelRouterProps) {
  const activePanel = usePanelStore((state) => state.activePanel);
  const hostRef = useRef<HTMLDivElement>(null);
  const firstRender = useRef(true);

  useEffect(() => {
    // Initial mount must not steal focus from the page/timeline. Only a real
    // panel change moves focus to the new panel heading.
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const heading = hostRef.current?.querySelector('h2');
    if (heading instanceof HTMLElement) heading.focus({ preventScroll: true });
  }, [activePanel]);

  return (
    <div
      ref={hostRef}
      className={styles.panelRouter}
      id={`panel-${activePanel}`}
      role="tabpanel"
      aria-labelledby={`panel-tab-${activePanel}`}
      tabIndex={-1}
      data-active-panel={activePanel}
    >
      {activePanel === 'risk' ? <RiskPanel risk={dataset.districtRisk} /> : null}
      {activePanel === 'validation' ? (
        <ValidationPanel scorecard={dataset.scorecard} />
      ) : null}
      {activePanel === 'provenance' ? <ProvenancePanel dataset={dataset} /> : null}
      {activePanel === 'methodology' ? <MethodologyPanel dataset={dataset} /> : null}
      {activePanel === 'layers' ? <LayersPanel dataset={dataset} /> : null}
    </div>
  );
}
