"""Every declared output schema must itself be a valid JSON Schema."""
from __future__ import annotations

import jsonschema

from baanh_pipeline.schemas import SCHEMAS


def test_schemas_are_valid_draft7():
    for name, schema in SCHEMAS.items():
        jsonschema.Draft7Validator.check_schema(schema)
        assert isinstance(schema, dict), name


def test_scenario_schema_accepts_config():
    from baanh_pipeline.config import load_config

    config = load_config()
    jsonschema.validate(config.scenario.raw, SCHEMAS["scenario.json"])
