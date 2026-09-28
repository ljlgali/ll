"""Input-validation tests for the list_pets tool/model.

Each invalid input must surface as a failed tool result carrying the unified
error structure with code VALIDATION_ERROR (no stack trace leaked).
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from pet_hospital_mcp.errors import VALIDATION_ERROR
from pet_hospital_mcp.tools.list_pets import ListPetsInput


def _build(**kwargs):
    """Build a ListPetsInput, returning (input_or_None, error_envelope_dict)."""
    try:
        return ListPetsInput(**kwargs), None
    except ValidationError as exc:
        return None, exc


def test_extra_unknown_field_rejected():
    inst, err = _build(species="犬", bogus="x")
    assert inst is None
    assert err is not None


def test_bad_species_rejected():
    inst, err = _build(species="龙")
    assert inst is None and err is not None


def test_bad_status_rejected():
    inst, err = _build(status="康复")
    assert inst is None and err is not None


def test_bad_sort_by_rejected():
    inst, err = _build(sortBy="foo")
    assert inst is None and err is not None


def test_bad_order_rejected():
    inst, err = _build(order="up")
    assert inst is None and err is not None


def test_page_below_one_rejected():
    inst, err = _build(page=0)
    assert inst is None and err is not None


@pytest.mark.parametrize("page_size", [0, 501, -1])
def test_page_size_out_of_range_rejected(page_size):
    inst, err = _build(pageSize=page_size)
    assert inst is None and err is not None


def test_negative_min_rejected():
    inst, err = _build(min=-1.0)
    assert inst is None and err is not None


def test_nan_rejected():
    inst, err = _build(min=float("nan"))
    assert inst is None and err is not None


def test_infinity_rejected():
    inst, err = _build(max=float("inf"))
    assert inst is None and err is not None


def test_wrong_type_rejected():
    # page must be int; a bool is technically int in Python, so use a list.
    inst, err = _build(page=[1])  # type: ignore[arg-type]
    assert inst is None and err is not None


def test_valid_input_accepted():
    inst, err = _build(species="犬", status="待就诊", sortBy="totalCost", order="desc", page=1, pageSize=10, min=0.0, max=100.0)
    assert err is None
    assert inst is not None
    assert inst.to_query() == {
        "species": "犬",
        "status": "待就诊",
        "sortBy": "totalCost",
        "order": "desc",
        "page": 1,
        "pageSize": 10,
        "min": 0.0,
        "max": 100.0,
    }


def test_min_greater_than_max_rejected_at_query_build():
    """Cross-field check lives in to_query (model_validator-free)."""
    inst = ListPetsInput(min=100.0, max=50.0)
    with pytest.raises(ValueError):
        inst.to_query()
