from app.config.ingestion_config import get_ingestion_settings, FILE_TYPES_CONFIG
from app.core.models.ingestion_settings import FileSchema, FileType
import pytest


def test_validate_key_fields_success():
    # Use an existing configured file type (should be valid by default)
    settings = get_ingestion_settings(FileType.DEFAULT_GROUP)
    assert settings.schema is not None
    # validation happens inside get_ingestion_settings, so no exception means success


def test_validate_key_fields_failure():
    # Temporarily inject an invalid key_fields into an existing FILE_TYPES_CONFIG entry
    key = FileType.DEFAULT_GROUP
    original_schema = FILE_TYPES_CONFIG[key].schema

    try:
        # set an invalid key_fields list that doesn't match mapped columns
        FILE_TYPES_CONFIG[key].schema = FileSchema(
            name="temp",
            column_mapping={"col_x": "X"},
            boolean_cols=[],
        )

        # now requesting settings should raise due to mismatched key_fields if set
        # ensure the schema has key_fields that will be considered invalid
        FILE_TYPES_CONFIG[key].schema.key_fields = ["MISSING_FIELD"]

        with pytest.raises(ValueError):
            get_ingestion_settings(key)
    finally:
        # restore original schema
        FILE_TYPES_CONFIG[key].schema = original_schema
