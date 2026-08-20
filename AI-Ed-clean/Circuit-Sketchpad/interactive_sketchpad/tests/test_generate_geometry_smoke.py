import shutil

import pytest

from geometry_components import generate
from geometry_components_utilities import apply_topology_edit

requires_latex = pytest.mark.skipif(
    shutil.which("lualatex") is None,
    reason="lualatex not installed -- render smoke tests need a LaTeX toolchain",
)

FULL_TOPOLOGY = """
Vertex A:(-1,1) above left
Vertex B:(1,1) above right
Vertex C:(-sqrt(2),0) below left
Vertex D:(sqrt(2),0) below right
Vertex O:(0,0) below
Vertex P:(0,1)

Edge A-B Label 2 above
Edge O-A Label sqrt(2) below left
Edge O-B Label sqrt(2) below right

Angle AOB=90

Circle O Center O Radius sqrt(2)

Arc APB
Arc AOB

Shaded Region APB BOA
"""


@requires_latex
def test_generate_full_topology_produces_a_png(tmp_path, monkeypatch):
    # generate() writes tikzdraw.{tex,pdf,png} into the current working
    # directory with fixed names -- run from a scratch dir so this doesn't
    # clobber a real session's output or another test running concurrently.
    monkeypatch.chdir(tmp_path)

    png_bytes = generate(FULL_TOPOLOGY, dpi=150, pretty=True)

    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


@requires_latex
def test_generate_after_incremental_edit_still_renders(tmp_path, monkeypatch):
    """
    A minimal end-to-end regression check for the edit_geometry path: apply
    an incremental edit the way chatbot.py does, then render the merged
    result and confirm it still produces a valid diagram instead of a
    malformed topology the renderer chokes on.
    """
    monkeypatch.chdir(tmp_path)

    base = "Vertex A:(0,0) below\nVertex B:(1,0) below\nEdge A-B"
    edited = apply_topology_edit(
        base,
        add_lines=["Vertex C:(0.5,1) above", "Edge B-C", "Edge C-A"],
        remove_keys=[],
    )

    png_bytes = generate(edited, dpi=150, pretty=True)

    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
