from __future__ import annotations
import pydantic
import pytest

import sys
import typing as t
from datetime import date
from collections import abc

from django_pydantic_field import fields

from django.db import models
from django.db.migrations.writer import MigrationWriter
from django.core.exceptions import FieldError

from .conftest import InnerSchema, SampleDataclass


class SampleModel(models.Model):
    sample_field: InnerSchema = fields.SchemaField()
    sample_list: t.List[InnerSchema] = fields.SchemaField()
    sample_seq: t.Sequence[InnerSchema] = fields.SchemaField(schema=t.List[InnerSchema])

    class Meta:
        app_label = "sample_app"


def test_sample_field():
    sample_field = fields.PydanticSchemaField(schema=InnerSchema)
    existing_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_encoded = '{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'

    assert sample_field.get_prep_value(existing_instance) == expected_encoded
    assert sample_field.to_python(expected_encoded) == existing_instance


def test_sample_field_with_raw_data():
    sample_field = fields.PydanticSchemaField(schema=InnerSchema)
    existing_raw = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}
    expected_encoded = '{"stub_str": "abc", "stub_int": 1, "stub_list": ["2022-07-01"]}'

    assert sample_field.get_prep_value(existing_raw) == expected_encoded
    assert sample_field.to_python(expected_encoded) == InnerSchema(**existing_raw)


def test_simple_model_field():
    sample_field = SampleModel._meta.get_field("sample_field")
    assert sample_field.schema == InnerSchema

    sample_list_field = SampleModel._meta.get_field("sample_list")
    assert sample_list_field.schema == t.List[InnerSchema]

    sample_seq_field = SampleModel._meta.get_field("sample_seq")
    assert sample_seq_field.schema == t.List[InnerSchema]

    existing_raw_field = {"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}
    existing_raw_list = [{"stub_str": "abc", "stub_list": []}]

    instance = SampleModel(sample_field=existing_raw_field, sample_list=existing_raw_list)

    expected_instance = InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])
    expected_list = [InnerSchema(stub_str="abc", stub_list=[])]

    assert instance.sample_field == expected_instance
    assert instance.sample_list == expected_list


def test_untyped_model_field_raises():
    with pytest.raises(FieldError):
        class UntypedModel(models.Model):
            sample_field = fields.SchemaField()

            class Meta:
                app_label = "sample_app"


@pytest.mark.parametrize("field", [
    fields.PydanticSchemaField(schema=InnerSchema, default=InnerSchema(stub_str="abc", stub_list=[date(2022, 7, 1)])),
    fields.PydanticSchemaField(schema=InnerSchema, default=(("stub_str", "abc"), ("stub_list", [date(2022, 7, 1)]))),
    fields.PydanticSchemaField(schema=InnerSchema, default={"stub_str": "abc", "stub_list": [date(2022, 7, 1)]}),
    fields.PydanticSchemaField(schema=InnerSchema, default=None),
    fields.PydanticSchemaField(schema=SampleDataclass, default={"stub_str": "abc", "stub_list": [date(2022, 7, 1)]})
])
def test_field_serialization(field):
    _, _, args, kwargs = field.deconstruct()

    reconstructed_field = fields.PydanticSchemaField(*args, **kwargs)
    assert field.get_default() == reconstructed_field.get_default()
    assert field.schema == reconstructed_field.schema

    deserialized_field = reconstruct_field(serialize_field(field))
    assert deserialized_field.get_default() == field.get_default()
    assert field.schema == deserialized_field.schema


@pytest.mark.skipif(sys.version_info < (3, 9), reason="Should test against builtin generic types")
@pytest.mark.parametrize("field", [
    fields.PydanticSchemaField(schema=list[InnerSchema], default=list),
    fields.PydanticSchemaField(schema=dict[str, InnerSchema], default=list),
    fields.PydanticSchemaField(schema=abc.Sequence[InnerSchema], default=list),
    fields.PydanticSchemaField(schema=abc.Mapping[str, InnerSchema], default=dict),
])
def test_field_builtin_annotations_serialization(field):
    _, _, args, kwargs = field.deconstruct()

    reconstructed_field = fields.PydanticSchemaField(*args, **kwargs)
    assert field.get_default() == reconstructed_field.get_default()
    assert field.schema == reconstructed_field.schema

    deserialized_field = reconstruct_field(serialize_field(field))
    assert deserialized_field.get_default() == field.get_default()
    assert field.schema == deserialized_field.schema


@pytest.mark.skipif(sys.version_info >= (3, 9), reason="Should test against builtin generic types")
@pytest.mark.parametrize("field", [
    fields.PydanticSchemaField(schema=t.List[InnerSchema], default=list),
    fields.PydanticSchemaField(schema=t.Dict[str, InnerSchema], default=list),
    fields.PydanticSchemaField(schema=t.Sequence[InnerSchema], default=list),
    fields.PydanticSchemaField(schema=t.Mapping[str, InnerSchema], default=dict),
])
def test_field_typing_annotations_serialization(field):
    _, _, args, kwargs = field.deconstruct()

    reconstructed_field = fields.PydanticSchemaField(*args, **kwargs)
    assert field.get_default() == reconstructed_field.get_default()
    assert field.schema == reconstructed_field.schema

    deserialized_field = reconstruct_field(serialize_field(field))
    assert deserialized_field.get_default() == field.get_default()
    assert field.schema == deserialized_field.schema


@pytest.mark.skipif(sys.version_info < (3, 9), reason="Typing-to-builtin migrations is reasonable only on py >= 3.9")
@pytest.mark.parametrize("old_field, new_field", [
    (
        fields.PydanticSchemaField(schema=t.List[InnerSchema], default=list),
        fields.PydanticSchemaField(schema=list[InnerSchema], default=list),
    ), (
        fields.PydanticSchemaField(schema=t.Dict[str, InnerSchema], default=list),
        fields.PydanticSchemaField(schema=dict[str, InnerSchema], default=list),
    ), (
        fields.PydanticSchemaField(schema=t.Sequence[InnerSchema], default=list),
        fields.PydanticSchemaField(schema=abc.Sequence[InnerSchema], default=list),
    ), (
        fields.PydanticSchemaField(schema=t.Mapping[str, InnerSchema], default=dict),
        fields.PydanticSchemaField(schema=abc.Mapping[str, InnerSchema], default=dict),
    ), (
        fields.PydanticSchemaField(schema=t.Mapping[str, InnerSchema], default=dict),
        fields.PydanticSchemaField(schema=abc.Mapping[str, InnerSchema], default=dict),
    )
])
def test_field_typing_to_builtin_serialization(old_field, new_field):
    _, _, args, kwargs = old_field.deconstruct()

    reconstructed_field = fields.PydanticSchemaField(*args, **kwargs)
    assert old_field.get_default() == new_field.get_default() == reconstructed_field.get_default()
    assert new_field.schema == reconstructed_field.schema

    deserialized_field = reconstruct_field(serialize_field(old_field))
    assert old_field.get_default() == deserialized_field.get_default() == new_field.get_default()
    assert new_field.schema == deserialized_field.schema


def serialize_field(field: fields.PydanticSchemaField) -> str:
    serialized_field, _ = MigrationWriter.serialize(field)
    return serialized_field


def reconstruct_field(field_repr: str) -> fields.PydanticSchemaField:
    return eval(field_repr, globals(), sys.modules)
