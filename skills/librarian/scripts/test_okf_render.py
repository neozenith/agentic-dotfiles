#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pytest>=8.0", "pytest-cov>=4.0",
#   "PyYAML>=6.0", "Jinja2>=3.1", "jsonschema>=4.0",
# ]
# ///
"""Tests for okf_render.py — real files in a tmp bundle, no mocks."""

from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

import okf_render

SCRIPT_DIR = Path(__file__).parent.resolve()
EXAMPLE_DIR = SCRIPT_DIR.parent / "resources" / "okf_yaml" / "example"


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    """A working copy of the shipped example bundle, sources only."""
    target = tmp_path / "records"
    target.mkdir()
    for src in sorted(EXAMPLE_DIR.glob("*.yml")):
        shutil.copy(src, target / src.name)
    return target


def write(bundle: Path, name: str, record: dict) -> None:
    (bundle / name).write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")


def first_record(bundle: Path) -> dict:
    return yaml.safe_load((bundle / "0001-validate-at-the-boundary.yml").read_text())


# ── yamlq ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["yes", "no", "12", "1.5", "- dash", "key: value", "", "trail "])
def test_yamlq_quotes_ambiguous_scalars(value: str) -> None:
    assert okf_render.yamlq(value).startswith('"')


@pytest.mark.parametrize("value", ["plain words", "internal/place (read back)", "a-slug"])
def test_yamlq_leaves_plain_scalars_alone(value: str) -> None:
    assert not okf_render.yamlq(value).startswith('"')


def test_yamlq_escapes_embedded_quotes() -> None:
    assert okf_render.yamlq('say "hi": now') == '"say \\"hi\\": now"'


# ── grouping ────────────────────────────────────────────────────────────


def test_explicit_group_wins_over_every_fallback() -> None:
    rec = {"group": "chosen", "plan_id": "P1.1", "tags": ["ignored"]}
    assert okf_render.group_of(rec, "plan_id") == "chosen"


def test_group_falls_back_to_plan_id_then_first_tag() -> None:
    assert okf_render.group_of({"plan_id": "P1.1", "tags": ["t"]}, "plan_id") == "P1.1"
    assert okf_render.group_of({"plan_id": "P1.1", "tags": ["t"]}, "tag") == "t"


def test_a_record_with_neither_is_ungrouped() -> None:
    assert okf_render.group_of({"tags": []}, "tag") == "ungrouped"


# ── validation ──────────────────────────────────────────────────────────


def test_the_shipped_example_validates(bundle: Path) -> None:
    assert okf_render.validate(okf_render.load(bundle), okf_render.DEFAULT_SCHEMA) == []


def test_an_unknown_key_is_an_error_not_a_silent_ignore(bundle: Path) -> None:
    rec = first_record(bundle)
    rec["tsatus"] = "accepted"  # the typo this schema exists to catch
    write(bundle, "0001-validate-at-the-boundary.yml", rec)
    errors = okf_render.validate(okf_render.load(bundle), okf_render.DEFAULT_SCHEMA)
    assert any("tsatus" in e for e in errors)


def test_a_description_ending_in_a_full_stop_is_rejected(bundle: Path) -> None:
    rec = first_record(bundle)
    rec["description"] = "A summary that wrongly ends in a full stop."
    write(bundle, "0001-validate-at-the-boundary.yml", rec)
    assert okf_render.validate(okf_render.load(bundle), okf_render.DEFAULT_SCHEMA)


def test_a_description_containing_a_dotted_path_is_accepted(bundle: Path) -> None:
    rec = first_record(bundle)
    rec["description"] = "Config resolves via env, then XDG, then ~/.config"
    write(bundle, "0001-validate-at-the-boundary.yml", rec)
    assert okf_render.validate(okf_render.load(bundle), okf_render.DEFAULT_SCHEMA) == []


def test_dates_validate_through_the_json_projection(bundle: Path) -> None:
    """YAML resolves an unquoted ISO date to a date object, not a string."""
    loaded = okf_render.load(bundle)
    assert isinstance(loaded[0]["accepted_on"], str)
    assert okf_render.validate(loaded, okf_render.DEFAULT_SCHEMA) == []


def test_a_record_with_no_cons_is_rejected(bundle: Path) -> None:
    rec = first_record(bundle)
    rec["consequences"]["cons"] = []
    write(bundle, "0001-validate-at-the-boundary.yml", rec)
    assert okf_render.validate(okf_render.load(bundle), okf_render.DEFAULT_SCHEMA)


# ── graph integrity ─────────────────────────────────────────────────────


def test_an_unresolvable_target_is_reported(bundle: Path) -> None:
    rec = first_record(bundle)
    rec["relates_to"] = [{"relation": "see_also", "target": "REC-9999"}]
    write(bundle, "0001-validate-at-the-boundary.yml", rec)
    assert okf_render.unresolved(okf_render.load(bundle))


def test_the_example_bundle_is_symmetric(bundle: Path) -> None:
    assert okf_render.asymmetries(okf_render.load(bundle)) == []


def test_a_one_way_edge_is_reported_with_the_inverse_it_lacks(bundle: Path) -> None:
    rec = yaml.safe_load((bundle / "0002-one-error-taxonomy.yml").read_text())
    rec["relates_to"] = []
    write(bundle, "0002-one-error-taxonomy.yml", rec)
    skew = okf_render.asymmetries(okf_render.load(bundle))
    assert skew[0]["source"] == "REC-0001"
    assert skew[0]["inverse"] == "depends_on"


def test_every_relation_has_an_inverse_and_a_prose_form() -> None:
    assert set(okf_render.INVERSE) == set(okf_render.PROSE)
    for relation, inverse in okf_render.INVERSE.items():
        assert okf_render.INVERSE[inverse] == relation


# ── cytoscape payload ───────────────────────────────────────────────────


def test_graph_nodes_and_edges_all_resolve(bundle: Path) -> None:
    graph = okf_render.cytoscape(okf_render.load(bundle), "tag")
    ids = {e["data"]["id"] for e in graph["elements"]}
    for el in graph["elements"]:
        data = el["data"]
        if "source" in data:
            assert data["source"] in ids and data["target"] in ids
        elif data.get("parent"):
            assert data["parent"] in ids


def test_group_colours_encode_data_and_repeat_per_group(bundle: Path) -> None:
    records = okf_render.load(bundle)
    graph = okf_render.cytoscape(records, "tag")
    colours = {e["data"]["colour"] for e in graph["elements"] if "source" not in e["data"]}
    assert len(colours) == 1  # both example records share one group


def test_more_groups_than_the_palette_cycles_rather_than_failing(bundle: Path) -> None:
    base = first_record(bundle)
    records = []
    for i in range(len(okf_render.GROUP_COLOURS) + 2):
        rec = copy.deepcopy(base)
        rec["id"] = f"REC-{i + 10:04d}"
        rec["slug"] = f"record-{i}"
        rec["group"] = f"group-{i}"
        rec["relates_to"] = []
        records.append(rec)
    graph = okf_render.cytoscape(records, "tag")
    assert len([e for e in graph["elements"] if "source" not in e["data"]]) == len(records) * 2


# ── rendering ───────────────────────────────────────────────────────────


def test_render_emits_every_artifact(bundle: Path) -> None:
    result = okf_render.render(bundle)
    assert result == {
        "records": 2,
        "edges": 2,
        "groups": 1,
        "asymmetries": [],
        "elements": 5,
    }
    for name in ("index.md", "graph.md", "graph.json"):
        assert (bundle / name).exists()
    assert (bundle / "0001-validate-at-the-boundary.md").exists()


def test_generated_markdown_is_okf_conformant(bundle: Path) -> None:
    okf_render.render(bundle)
    text = (bundle / "0001-validate-at-the-boundary.md").read_text()
    assert text.startswith("---\n")
    frontmatter = yaml.safe_load(text.split("---\n")[1])
    assert frontmatter["type"] == "Architecture Decision"
    assert frontmatter["title"]


def test_reserved_index_carries_no_frontmatter(bundle: Path) -> None:
    okf_render.render(bundle)
    assert not (bundle / "index.md").read_text().startswith("---\n")


def test_a_null_plan_id_omits_the_key_rather_than_writing_none(bundle: Path) -> None:
    """`plan_id: None` would parse as the string 'None', not as null."""
    okf_render.render(bundle)
    text = (bundle / "0001-validate-at-the-boundary.md").read_text()
    assert "None" not in text.split("---\n")[1]
    assert "plan_id" not in yaml.safe_load(text.split("---\n")[1])


def test_a_present_plan_id_is_emitted(bundle: Path) -> None:
    rec = first_record(bundle)
    rec["plan_id"] = "P1.1"
    write(bundle, "0001-validate-at-the-boundary.yml", rec)
    okf_render.render(bundle)
    text = (bundle / "0001-validate-at-the-boundary.md").read_text()
    assert yaml.safe_load(text.split("---\n")[1])["plan_id"] == "P1.1"


def test_the_author_reaches_the_generated_frontmatter(bundle: Path) -> None:
    okf_render.render(bundle, author="process:ci")
    text = (bundle / "0001-validate-at-the-boundary.md").read_text()
    assert "process:ci" in text


def test_rendering_is_deterministic(bundle: Path) -> None:
    okf_render.render(bundle)
    first = (bundle / "0001-validate-at-the-boundary.md").read_text()
    graph = (bundle / "graph.json").read_text()
    okf_render.render(bundle)
    assert (bundle / "0001-validate-at-the-boundary.md").read_text() == first
    assert (bundle / "graph.json").read_text() == graph


def test_the_shipped_example_matches_its_committed_output(bundle: Path) -> None:
    """The golden fixture: a ported generator must reproduce these bytes."""
    okf_render.render(bundle)
    for generated in sorted(bundle.glob("*.md")):
        assert generated.read_text() == (EXAMPLE_DIR / generated.name).read_text(), (
            f"{generated.name} drifted from the committed golden; "
            "re-run okf_render.py over resources/okf_yaml/example if intended"
        )
    assert json.loads((bundle / "graph.json").read_text()) == json.loads(
        (EXAMPLE_DIR / "graph.json").read_text()
    )


# ── failure paths ───────────────────────────────────────────────────────


def test_an_empty_directory_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no records found"):
        okf_render.render(tmp_path)


def test_an_invalid_record_stops_the_build(bundle: Path) -> None:
    rec = first_record(bundle)
    rec["status"] = "vaguely-agreed"
    write(bundle, "0001-validate-at-the-boundary.yml", rec)
    with pytest.raises(ValueError, match="did not validate"):
        okf_render.render(bundle)
    assert not (bundle / "0001-validate-at-the-boundary.md").exists()


def test_index_yml_is_not_mistaken_for_a_record(bundle: Path) -> None:
    (bundle / "index.yml").write_text("bundle: a catalogue\n", encoding="utf-8")
    assert len(okf_render.load(bundle)) == 2


# ── CLI ─────────────────────────────────────────────────────────────────


def test_cli_renders_and_reports(bundle: Path, caplog: pytest.LogCaptureFixture) -> None:
    args = okf_render.build_parser().parse_args([str(bundle)])
    with caplog.at_level("INFO"):
        assert okf_render.main(args) == 0
    assert "rendered 2 records" in caplog.text


def test_cli_returns_one_on_invalid_records(bundle: Path) -> None:
    rec = first_record(bundle)
    rec["status"] = "nope"
    write(bundle, "0001-validate-at-the-boundary.yml", rec)
    args = okf_render.build_parser().parse_args([str(bundle), "--verbose"])
    assert okf_render.main(args) == 1


def test_cli_reports_one_way_edges(bundle: Path, caplog: pytest.LogCaptureFixture) -> None:
    rec = yaml.safe_load((bundle / "0002-one-error-taxonomy.yml").read_text())
    rec["relates_to"] = []
    write(bundle, "0002-one-error-taxonomy.yml", rec)
    args = okf_render.build_parser().parse_args([str(bundle), "--group-by", "plan_id"])
    with caplog.at_level("INFO"):
        assert okf_render.main(args) == 0
    assert "one-way" in caplog.text


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
