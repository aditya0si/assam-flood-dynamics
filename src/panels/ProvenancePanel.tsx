import type { Dataset } from '../data/types';
import type { ProvenanceEntry } from '../data/schemas';
import { HONESTY_CHIP, badgeFor } from '../data/labels';
import styles from './panels.module.css';

interface ProvenancePanelProps {
  dataset: Dataset;
}

const REQUIRED_ENTRIES = ['terrain', 'boundaries', 'rivers', 'flood', 'risk'] as const;

function entryOrder(entry: ProvenanceEntry): number {
  const index = REQUIRED_ENTRIES.indexOf(entry.id as (typeof REQUIRED_ENTRIES)[number]);
  return index === -1 ? REQUIRED_ENTRIES.length + 1 : index;
}

function stageCodes(entry: ProvenanceEntry): string {
  return entry.pipeline.map((stage) => `S${stage.stage}`).join(' → ') || 'reference only';
}

export function ProvenancePanel({ dataset }: ProvenancePanelProps) {
  const entries = [...dataset.provenance.entries]
    .filter((entry) => REQUIRED_ENTRIES.includes(entry.id as (typeof REQUIRED_ENTRIES)[number]))
    .sort((left, right) => entryOrder(left) - entryOrder(right));

  return (
    <div className={styles.panelBody}>
      <div className={styles.panelIntro}>
        <div className={styles.panelTitleRow}>
          <h2 className={styles.panelTitle} tabIndex={-1}>
            Provenance
          </h2>
          <span className={styles.notForecastSmall}>{HONESTY_CHIP}</span>
        </div>
        <p className={styles.honestyStatement}>
          This is <strong>{HONESTY_CHIP}</strong>. It is a synthetic-monsoon, terrain-derived
          explanatory scenario, not an operational warning, not a record of a real event, and not a
          prediction of what will happen.
        </p>
        <p className={styles.panelLead}>
          Source → processing stage → committed file for each dataset. Dataset{' '}
          <code>{dataset.provenance.dataset_version}</code>, generated{' '}
          <code>{dataset.provenance.generated_at}</code>.
        </p>
      </div>

      <div className={styles.provenanceList}>
        {entries.map((entry) => (
          <article key={entry.id} className={styles.provenanceCard} data-prov-entry={entry.id}>
            <header className={styles.provenanceHead}>
              <span className={styles.classBadge}>{badgeFor(entry.class)}</span>
              <h3 className={styles.provenanceTitle}>{entry.dataset}</h3>
            </header>
            <p className={styles.sourceLine}>
              <span className={styles.fieldLabel}>Source</span>
              <span>{entry.source_name}</span>
            </p>
            <p className={styles.stageLine}>
              <span className={styles.fieldLabel}>Stage</span>
              <span>
                {entry.pipeline.map((stage) => (
                  <span key={stage.stage} className={styles.stageChip} title={stage.command}>
                    S{stage.stage}
                  </span>
                ))}
                {entry.pipeline.length === 0 ? 'reference only' : null}
              </span>
              <span className={styles.stageSummary}>{stageCodes(entry)}</span>
            </p>
            <ul className={styles.fileList}>
              {entry.output_paths.map((path) => (
                <li key={path}>
                  <code>{path}</code>
                </li>
              ))}
            </ul>
            <details className={styles.provenanceDetails}>
              <summary>Licence & notes</summary>
              <p>{entry.licence}</p>
              <p>{entry.notes}</p>
            </details>
          </article>
        ))}
      </div>

      <section className={styles.subSection}>
        <h3 className={styles.subTitle}>Model assumptions</h3>
        <ul className={styles.assumptionList}>
          {dataset.scenario.assumptions.map((assumption, index) => (
            <li key={index}>{assumption}</li>
          ))}
        </ul>
      </section>

      <p className={styles.panelFoot}>
        No hidden live feed, agency identifier or event record is used. Derived layers carry the
        {' '}
        {badgeFor(dataset.districtRisk.class)} and {badgeFor(dataset.summary.class)} badges at the
        point of use.
      </p>
    </div>
  );
}
