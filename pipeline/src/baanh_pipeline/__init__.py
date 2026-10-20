"""Baanh offline data pipeline (phase A).

The package is deliberately a set of small, ordered stage modules.  Each stage
is invoked through ``python -m baanh_pipeline.cli <subcommand>`` and writes a
provenance fragment under ``pipeline/work/provenance/``.
"""

__version__ = "1.0.0"
__pipeline_version__ = "1.0.0"
