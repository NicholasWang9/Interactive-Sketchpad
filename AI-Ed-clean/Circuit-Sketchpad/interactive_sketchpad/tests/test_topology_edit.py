from geometry_components_utilities import apply_topology_edit, topology_line_key


def test_add_new_line_appends():
    result = apply_topology_edit("Vertex A:(0,0)", ["Vertex B:(1,1)"], [])
    assert result == "Vertex A:(0,0)\nVertex B:(1,1)"


def test_add_replaces_line_with_same_key_instead_of_duplicating():
    current = "Vertex A:(0,0)\nVertex B:(1,1)"
    result = apply_topology_edit(current, ["Vertex A:(2,2)"], [])
    assert result == "Vertex A:(2,2)\nVertex B:(1,1)"
    assert result.count("Vertex A") == 1


def test_replaced_line_keeps_its_original_position():
    current = "Vertex A:(0,0)\nVertex B:(1,1)\nVertex C:(2,2)"
    result = apply_topology_edit(current, ["Vertex B:(9,9)"], [])
    assert result == "Vertex A:(0,0)\nVertex B:(9,9)\nVertex C:(2,2)"


def test_remove_by_key():
    current = "Vertex A:(0,0)\nAngle ABC=90"
    result = apply_topology_edit(current, [], ["Angle ABC"])
    assert result == "Vertex A:(0,0)"


def test_removing_unknown_key_is_a_no_op():
    current = "Vertex A:(0,0)"
    result = apply_topology_edit(current, [], ["Angle XYZ"])
    assert result == current


def test_shaded_region_removed_by_exact_text_only():
    current = "Vertex A:(0,0)\nShaded Region ABC"
    # Not an exact match -- should NOT remove the shaded region line.
    result = apply_topology_edit(current, [], ["Shaded Region abc"])
    assert "Shaded Region ABC" in result

    result = apply_topology_edit(current, [], ["Shaded Region ABC"])
    assert "Shaded Region ABC" not in result


def test_noop_edit_returns_identical_topology():
    current = "Vertex A:(0,0)\nEdge A-B"
    result = apply_topology_edit(current, ["Vertex A:(0,0)"], [])
    assert result == current


def test_blank_lines_in_source_are_dropped():
    current = "Vertex A:(0,0)\n\n\nVertex B:(1,1)"
    result = apply_topology_edit(current, [], [])
    assert result == "Vertex A:(0,0)\nVertex B:(1,1)"


def test_edge_key_is_order_independent():
    # A moved/re-labeled edge given as "Edge B-A" must replace an existing
    # "Edge A-B" line rather than creating a duplicate, since a segment has
    # no direction.
    assert topology_line_key("Edge A-B") == topology_line_key("Edge B-A")

    current = "Edge A-B"
    result = apply_topology_edit(current, ["Edge B-A Label 5 above"], [])
    assert result == "Edge B-A Label 5 above"
    assert result.count("Edge") == 1


def test_add_then_remove_in_separate_calls_nets_to_removed():
    current = "Vertex A:(0,0)"
    after_add = apply_topology_edit(current, ["Vertex B:(1,1)"], [])
    after_remove = apply_topology_edit(after_add, [], ["Vertex B"])
    assert after_remove == "Vertex A:(0,0)"


def test_add_and_remove_same_key_in_one_call_favors_add():
    # remove_keys is applied before add_lines within a single call, so a key
    # present in both nets to "added" (present), not "removed" -- documenting
    # this order dependency since it's easy to assume the opposite.
    current = "Vertex A:(0,0)"
    result = apply_topology_edit(current, ["Vertex B:(1,1)"], ["Vertex B"])
    assert result == "Vertex A:(0,0)\nVertex B:(1,1)"
