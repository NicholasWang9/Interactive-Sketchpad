import pytest

from geometry_components_vertices import point
from geometry_components_arcs_and_angles import parse_angles_from_topology


def _vertices(coords):
    return {name: point(xy) for name, xy in coords.items()}


def test_angle_matching_stated_measure_is_accepted_unchanged():
    # A at 90 degrees from O, B at 0 degrees from O: sweeping clockwise from
    # A to B is exactly 90 degrees, matching "Angle AOB=90" as given.
    vertices = _vertices({"A": (0, 1), "O": (0, 0), "B": (1, 0)})
    angles = parse_angles_from_topology("Angle AOB=90", {"vertices": vertices})

    assert len(angles) == 1
    assert angles[0].measure == 90
    assert angles[0].counterclockwise_point == "A"
    assert angles[0].clockwise_point == "B"


def test_reflex_complement_match_auto_swaps_endpoints():
    # Same 90-degree corner, but with the ccw/cw roles given backwards --
    # the clockwise sweep from A to B here is 270 (the reflex complement of
    # the stated 90), so parsing should swap the endpoints rather than
    # reject a diagram that is actually correct, just mislabeled.
    vertices = _vertices({"A": (1, 0), "O": (0, 0), "B": (0, 1)})
    angles = parse_angles_from_topology("Angle AOB=90", {"vertices": vertices})

    assert len(angles) == 1
    assert angles[0].counterclockwise_point == "B"
    assert angles[0].clockwise_point == "A"


def test_coordinates_inconsistent_with_stated_measure_raises():
    # The actual angle at O between these three points is ~315 degrees
    # going clockwise from A to B -- neither 90 nor its reflex complement
    # (270), so this is a genuine mismatch that must be surfaced, not
    # silently rendered as a right angle.
    vertices = _vertices({"A": (1, 0), "O": (0, 0), "B": (1, 1)})

    with pytest.raises(ValueError):
        parse_angles_from_topology("Angle AOB=90", {"vertices": vertices})


def test_symbolic_measure_is_not_validated():
    # A non-numeric measure (e.g. an unknown/variable angle the student is
    # meant to solve for) has nothing to check coordinates against, so it
    # must be accepted as-is regardless of the actual coordinate geometry.
    vertices = _vertices({"A": (1, 0), "O": (0, 0), "B": (1, 1)})
    angles = parse_angles_from_topology("Angle AOB=x", {"vertices": vertices})

    assert len(angles) == 1
    assert angles[0].measure == "x"


def test_unknown_vertex_in_angle_is_skipped_not_raised():
    vertices = _vertices({"A": (1, 0), "O": (0, 0)})  # "B" missing
    angles = parse_angles_from_topology("Angle AOB=90", {"vertices": vertices})
    assert angles == []
