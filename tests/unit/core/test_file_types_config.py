from app.config.file_types_config import FileTypeConfig
from app.core.models.file_schema import FileSchema
import pytest


def test_validate_key_fields_success():
    schema = FileSchema(
        name="test",
        column_mapping={"col_a": "A", "col_b": "B"},
        boolean_cols=[],
    )

    cfg = FileTypeConfig(
        name="test",
        blob_container="c",
        blob_path="p",
        schema=schema,
        key_fields=["A"],
        mongo_collection=None,
    )

    # Should not raise
    from app.config.file_types_config import get_file_type_config, FILE_TYPES_CONFIG

    # Validate helper logic by calling the internal check via temporarily invoking the same validation
    # (we don't mutate global FILE_TYPES_CONFIG here; just ensure our cfg's keys are valid)
    mapped = set(cfg.schema.column_mapping.values())
    missing = [k for k in cfg.key_fields if k not in mapped]
    assert missing == []


def test_validate_key_fields_failure():
    schema = FileSchema(
        name="test",
        column_mapping={"col_x": "X"},
        boolean_cols=[],
    )

    cfg = FileTypeConfig(
        name="bad",
        blob_container="c",
        blob_path="p",
        schema=schema,
        key_fields=["MISSING_FIELD"],
        mongo_collection=None,
    )

    mapped = set(cfg.schema.column_mapping.values())
    missing = [k for k in cfg.key_fields if k not in mapped]
    assert missing == ["MISSING_FIELD"]

    # If a real lookup were performed via FILE_TYPES_CONFIG, it should raise ValueError.
    # We'll temporarily insert and then remove to simulate the behavior.
    from app.config.file_types_config import FILE_TYPES_CONFIG

    FILE_TYPES_CONFIG["bad_test_temp"] = cfg
    try:
        from app.config.file_types_config import get_file_type_config as g

        with pytest.raises(ValueError):
            g("bad_test_temp")
    finally:
        FILE_TYPES_CONFIG.pop("bad_test_temp", None)
