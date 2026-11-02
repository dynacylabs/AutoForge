"""Tests for autoforge.Helper.FilamentHelper.

Consolidated from the former test_filament_helper.py and the filament half
of test_filament_and_output.py.
"""

import json
import types

import numpy as np
import pytest

pandas = pytest.importorskip("pandas")
torch = pytest.importorskip("torch")

from autoforge.Helper.FilamentHelper import (
    count_distinct_colors,
    count_swaps,
    extract_colors_from_swatches,
    hex_to_rgb,
    load_materials,
    load_materials_data,
    swatch_data_to_table,
)


def _csv_args(tmp_path, rows=None):
    rows = rows or [
        {"Brand": "BrandA", "Name": "Mat1", "Transmissivity": 0.5, "Color": "#112233"},
        {"Brand": "BrandB", "Name": "Mat2", "Transmissivity": 1.0, "Color": "#445566"},
        {"Brand": "BrandC", "Name": "Mat3", "Transmissivity": 0.1, "Color": "#778899"},
    ]
    csv_path = tmp_path / "materials.csv"
    pandas.DataFrame(rows).to_csv(csv_path, index=False)
    return types.SimpleNamespace(csv_file=str(csv_path), json_file="")


# --------------------------------------------------------------------------
# hex_to_rgb
# --------------------------------------------------------------------------


def test_hex_to_rgb_exact_values():
    assert hex_to_rgb("#FFFFFF") == [1.0, 1.0, 1.0]
    assert hex_to_rgb("#000000") == [0.0, 0.0, 0.0]
    r, g, b = hex_to_rgb("#8040ff")
    assert (r, g, b) == (128 / 255, 64 / 255, 255 / 255)


def test_hex_to_rgb_tolerates_missing_hash():
    assert hex_to_rgb("00ff00") == [0.0, 1.0, 0.0]


@pytest.mark.parametrize("hx", ["#ff0000", "#123456", "#abcdef", "#0A0B0C"])
def test_hex_to_rgb_always_in_unit_range(hx):
    rgb = hex_to_rgb(hx)
    assert len(rgb) == 3
    assert all(0.0 <= c <= 1.0 for c in rgb)


# --------------------------------------------------------------------------
# count_distinct_colors / count_swaps
# --------------------------------------------------------------------------


def test_count_distinct_colors():
    assert count_distinct_colors(torch.tensor([0, 0, 1, 2, 2, 2, 5])) == 4
    assert count_distinct_colors(torch.tensor([3, 3, 3])) == 1


def test_count_swaps_counts_transitions():
    # transitions at 1->2, 3->4, 6->7
    assert count_swaps(torch.tensor([1, 1, 2, 2, 3, 3, 3, 1])) == 3
    assert count_swaps(torch.tensor([0, 0, 0])) == 0


# --------------------------------------------------------------------------
# load_materials (CSV + JSON)
# --------------------------------------------------------------------------


def test_load_materials_from_csv(tmp_path):
    args = _csv_args(tmp_path)
    colors, tds, names, hexes = load_materials(args)
    assert colors.shape == (3, 3)
    assert tds.shape == (3,)
    assert names == ["BrandA - Mat1", "BrandB - Mat2", "BrandC - Mat3"]
    assert hexes == ["#112233", "#445566", "#778899"]
    assert tds.tolist() == [0.5, 1.0, 0.1]
    # First row #112233 -> (0x11, 0x22, 0x33) / 255
    assert np.allclose(colors[0], [0x11 / 255, 0x22 / 255, 0x33 / 255])


def test_load_materials_accepts_td_column_alias(tmp_path):
    args = _csv_args(
        tmp_path,
        rows=[
            {"Brand": "B", "Name": "M", "TD": 0.9, "Color": "#010203"},
        ],
    )
    _colors, tds, _names, _hexes = load_materials(args)
    assert tds.tolist() == [0.9]


def test_load_materials_data_records(tmp_path):
    args = _csv_args(tmp_path)
    records = load_materials_data(args)
    assert isinstance(records, list) and len(records) == 3
    assert {r["Brand"] for r in records} == {"BrandA", "BrandB", "BrandC"}


def test_load_materials_from_json(tmp_path):
    json_path = tmp_path / "filaments.json"
    json_path.write_text(
        json.dumps(
            {
                "Filaments": [
                    {"Brand": "J", "Name": "One", "Transmissivity": 0.3, "Color": "#ff0000"},
                    {"Brand": "J", "Name": "Two", "Transmissivity": 0.6, "Color": "#00ff00"},
                ]
            }
        )
    )
    args = types.SimpleNamespace(csv_file="", json_file=str(json_path))
    colors, tds, names, _hexes = load_materials(args)
    assert colors.shape == (2, 3)
    assert names == ["J - One", "J - Two"]
    assert tds.tolist() == [0.3, 0.6]


def test_load_materials_json_without_filaments_key_exits(tmp_path):
    json_path = tmp_path / "bad.json"
    json_path.write_text(json.dumps({"not_filaments": []}))
    args = types.SimpleNamespace(csv_file="", json_file=str(json_path))
    with pytest.raises(SystemExit):
        load_materials(args)


# --------------------------------------------------------------------------
# filamentcolors.com swatch helpers
# --------------------------------------------------------------------------


def test_extract_colors_from_swatches():
    swatches = [
        {
            "td": 0.5,
            "manufacturer": {"name": "BrandX"},
            "color_name": "Redish",
            "hex_color": "ff0000",
        },
        {
            "td": 0.7,
            "manufacturer": {"name": "BrandY"},
            "color_name": "Greenish",
            "hex_color": "00ff00",
        },
    ]
    colors, tds, names, hexes = extract_colors_from_swatches(swatches)
    assert colors.shape == (2, 3)
    assert tds.tolist() == [0.5, 0.7]
    assert names == ["BrandX - Redish", "BrandY - Greenish"]
    assert np.allclose(colors[0], [1.0, 0.0, 0.0])


def test_extract_colors_from_swatches_drops_entries_without_td():
    swatches = [
        {"td": 0.0, "manufacturer": {"name": "B"}, "color_name": "X", "hex_color": "000000"},
        {"td": 0.4, "manufacturer": {"name": "B"}, "color_name": "Y", "hex_color": "ffffff"},
    ]
    colors, tds, _names, _hexes = extract_colors_from_swatches(swatches)
    assert colors.shape == (1, 3)
    assert tds.tolist() == [0.4]


def test_swatch_data_to_table():
    swatches = [
        {
            "td": 0.4,
            "manufacturer": {"name": "B"},
            "color_name": "Blue",
            "hex_color": "0000ff",
        }
    ]
    table = swatch_data_to_table(swatches)
    assert table[0]["HexColor"] == "#0000ff"
