import pytest

from geometry_components_edges import parse_edges_from_topology
from geometry_components_utilities import label_to_latex


def test_plain_edge_has_no_label():
    edges = parse_edges_from_topology("Edge A-B", {})
    assert edges == [["A", "B", None, None]]


def test_edge_with_label_and_position():
    edges = parse_edges_from_topology("Edge A-B Label 4*sqrt(3) below", {})
    endpoint1, endpoint2, label, position = edges[0]
    assert (endpoint1, endpoint2) == ("A", "B")
    assert position == "below"
    assert "sqrt" in label


def test_edge_label_without_position_leaves_position_none():
    edges = parse_edges_from_topology("Edge A-B Label 5", {})
    assert edges[0][2] is not None
    assert edges[0][3] is None


def test_multiple_edges_in_one_topology():
    topology = "Edge A-B Label 2 above\nEdge B-C\nEdge C-A Label 3 left"
    edges = parse_edges_from_topology(topology, {})
    assert [(e[0], e[1]) for e in edges] == [("A", "B"), ("B", "C"), ("C", "A")]


def test_fraction_label_renders_as_frac_not_division():
    assert label_to_latex("25/2") == r"\frac{25}{2}"


def test_invalid_label_expression_raises_value_error():
    with pytest.raises(ValueError):
        label_to_latex("2 +")
