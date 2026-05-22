#!/usr/bin/env python3
import argparse
import os
import random
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Any, Tuple, List

# =====================
# Series–parallel model
# =====================

def R() -> Dict[str, Any]:
    return {"t": "R"}

def S(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    return {"t": "S", "a": a, "b": b}

def P(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    return {"t": "P", "a": a, "b": b}

def expr(e: Dict[str, Any]) -> str:
    """Expression string: S -> '+', P -> '//'."""
    if e["t"] == "R":
        return "R"
    if e["t"] == "S":
        return f"({expr(e['a'])}+{expr(e['b'])})"
    return f"({expr(e['a'])}//{expr(e['b'])})"

def key(e: Dict[str, Any]) -> str:
    """Canonical key. Series ordered, parallel commutative."""
    if e["t"] == "R":
        return "R"
    ka, kb = key(e["a"]), key(e["b"])
    if e["t"] == "S":
        return f"S({ka},{kb})"
    # Parallel commutative
    return f"P({ka},{kb})" if ka < kb else f"P({kb},{ka})"

@lru_cache(None)
def gen(n: int) -> Tuple[Dict[str, Any], ...]:
    """Generate all unique SP trees with n resistors."""
    if n == 1:
        return (R(),)
    res: List[Dict[str, Any]] = []
    seen = set()
    for k in range(1, n):
        for a in gen(k):
            for b in gen(n - k):
                s = S(a, b)
                ks = key(s)
                if ks not in seen:
                    seen.add(ks)
                    res.append(s)
                p = P(a, b)
                kp = key(p)
                if kp not in seen:
                    seen.add(kp)
                    res.append(p)
    res.sort(key=key)
    return tuple(res)

# =================
# Pretty / flatten
# =================

def flatten_series(e: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten associative series: S(S(a,b),c) -> [a,b,c] (order preserved)."""
    if e["t"] == "S":
        return flatten_series(e["a"]) + flatten_series(e["b"])
    return [e]

def flatten_parallel(e: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten associative parallel: P(P(a,b),c) -> [a,b,c] (order preserved)."""
    if e["t"] == "P":
        return flatten_parallel(e["a"]) + flatten_parallel(e["b"])
    return [e]

def expr_pretty(e: Dict[str, Any]) -> str:
    """
    Pretty expression that reduces nesting by treating S and P as n-ary.
    Example: (((R//R)//R)//R) -> (R//R//R//R)
    """
    if e["t"] == "R":
        return "R"
    if e["t"] == "S":
        parts = [expr_pretty(x) for x in flatten_series(e)]
        return "(" + "+".join(parts) + ")"
    parts = [expr_pretty(x) for x in flatten_parallel(e)]
    return "(" + "//".join(parts) + ")"

def tikz_num(x: float, nd: int = 4) -> str:
    # clamp tiny values to 0 to avoid -4.44e-16 and -0.0000
    if abs(x) < 1e-9:
        x = 0.0
    s = f"{x:.{nd}f}"
    if s.startswith("-0."):
        s = s[1:]
    return s

# ======================
# Parse explicit topology
# ======================

class TopologyParseError(ValueError):
    pass

_TOKEN_RE = re.compile(r"\s*(//|\+|\(|\)|R)\s*")

def tokenize_topology(s: str) -> List[str]:
    pos = 0
    toks: List[str] = []
    while pos < len(s):
        m = _TOKEN_RE.match(s, pos)
        if not m:
            raise TopologyParseError(f"Unexpected character at position {pos}: {s[pos:pos+20]!r}")
        toks.append(m.group(1))
        pos = m.end()
    return toks

def parse_topology(s: str) -> Dict[str, Any]:
    """
    Grammar (left associative):
      expr   := term (('+' | '//') term)*
      term   := 'R' | '(' expr ')'
    """
    toks = tokenize_topology(s)
    i = 0

    def peek() -> str:
        return toks[i] if i < len(toks) else ""

    def consume(expected: str = "") -> str:
        nonlocal i
        if i >= len(toks):
            raise TopologyParseError("Unexpected end of input")
        tok = toks[i]
        if expected and tok != expected:
            raise TopologyParseError(f"Expected {expected!r}, got {tok!r}")
        i += 1
        return tok

    def parse_term() -> Dict[str, Any]:
        tok = peek()
        if tok == "R":
            consume("R")
            return R()
        if tok == "(":
            consume("(")
            node = parse_expr()
            consume(")")
            return node
        raise TopologyParseError(f"Expected 'R' or '(', got {tok!r}")

    def parse_expr() -> Dict[str, Any]:
        node = parse_term()
        while True:
            tok = peek()
            if tok == "+":
                consume("+")
                rhs = parse_term()
                node = S(node, rhs)
            elif tok == "//":
                consume("//")
                rhs = parse_term()
                node = P(node, rhs)
            else:
                break
        return node

    tree = parse_expr()
    if i != len(toks):
        raise TopologyParseError(f"Trailing tokens: {toks[i:]}")
    return tree

def count_resistors(e: Dict[str, Any]) -> int:
    if e["t"] == "R":
        return 1
    return count_resistors(e["a"]) + count_resistors(e["b"])

# =================
# Drawing routines
# =================

@dataclass(frozen=True)
class DrawOut:
    w: float          # width in cm
    h: float          # height in cm (vertical span of subtree)
    tex: str          # circuitikz drawing commands

def draw(e: Dict[str, Any], pretty: bool = False) -> DrawOut:
    PAD = 0.6
    series_gap = 0.4
    parallel_gap = 1.6  # used as "gap" in compact packing

    if e["t"] == "R":
        return DrawOut(
            w=2.0,
            h=0.0,
            tex=r"\draw (0,0) -- (0.4,0) to[R] (1.6,0)--(2,0);"
        )

    # -------------------------
    # N-ary SERIES (flattened)
    # -------------------------
    if e["t"] == "S":
        kids = flatten_series(e) if pretty else [e["a"], e["b"]]
        drawn = [draw(k, pretty) for k in kids]

        w = sum(d.w for d in drawn) + series_gap * (len(drawn) - 1)
        h = max((d.h for d in drawn), default=0.0)

        tex_parts: List[str] = []
        x = 0.0
        for idx, d in enumerate(drawn):
            if idx > 0:
                tex_parts.append(
                    rf"\draw ({tikz_num(x)},0) -- ({tikz_num(x + series_gap)},0);"
                )
                x += series_gap

            tex_parts.append(rf"\begin{{scope}}[xshift={tikz_num(x)}cm]")
            tex_parts.append(d.tex)
            tex_parts.append(r"\end{scope}")
            x += d.w

        return DrawOut(w=w, h=h, tex="\n".join(tex_parts))

    # ---------------------------
    # N-ary PARALLEL (flattened)
    # compact packing (no even spacing)
    # ---------------------------
    assert e["t"] == "P"
    kids = flatten_parallel(e) if pretty else [e["a"], e["b"]]
    drawn = [draw(k, pretty) for k in kids]

    pad = PAD if pretty else 0.0

    inner_w = max((d.w for d in drawn), default=0.0)
    w = inner_w + 2 * pad

    min_branch_h = 0.9
    gap = parallel_gap

    eff_h = [max(d.h, min_branch_h) for d in drawn]
    total_h = sum(eff_h) + gap * (len(eff_h) - 1) if drawn else 0.0
    h = total_h

    centers: List[float] = []
    if drawn:
        y = total_h / 2.0 - eff_h[0] / 2.0
        centers.append(y)
        for i in range(1, len(drawn)):
            y -= (eff_h[i - 1] / 2.0 + gap + eff_h[i] / 2.0)
            centers.append(y)

    tex_parts: List[str] = []

    for c, d in zip(centers, drawn):
        tex_parts.append(
            rf"\begin{{scope}}[xshift={tikz_num(pad)}cm, yshift={tikz_num(c)}cm]"
        )
        tex_parts.append(d.tex)
        tex_parts.append(r"\end{scope}")

        # Extend shorter branches to inner_w
        tex_parts.append(
            rf"\draw ({tikz_num(pad + d.w)},{tikz_num(c)}) -- ({tikz_num(pad + inner_w)},{tikz_num(c)});"
        )

    # Left interface wires
    if pad > 0:
        for c in centers:
            tex_parts.append(
                rf"\draw (0,{tikz_num(c)}) -- ({tikz_num(pad)},{tikz_num(c)});"
            )

    # Left bus
    if centers:
        tex_parts.append(
            rf"\draw (0,{tikz_num(centers[0])}) -- (0,{tikz_num(centers[-1])});"
        )

    # Right interface wires
    if pad > 0:
        for c in centers:
            tex_parts.append(
                rf"\draw ({tikz_num(pad + inner_w)},{tikz_num(c)}) -- ({tikz_num(w)},{tikz_num(c)});"
            )

    # Right bus
    if centers:
        tex_parts.append(
            rf"\draw ({tikz_num(w)},{tikz_num(centers[0])}) -- ({tikz_num(w)},{tikz_num(centers[-1])});"
        )

    return DrawOut(w=w, h=h, tex="\n".join(tex_parts))

# =====================
# TeX document template
# =====================

def choose_scale_and_page(w: float, h: float, show_label: bool):
    target_w = 16.0
    target_h = 22.0 if show_label else 23.0
    extra_w = 3.0
    extra_h = 6.0

    s = min(1.0, target_w / (w + extra_w), target_h / (h + extra_h))
    min_scale = 0.65
    if s >= min_scale:
        return s, "letter"
    else:
        return min_scale, "large"

def make_tex_document(circuit_snippet: str, w: float, h: float, title: str, *, show_label: bool) -> str:
    scale, page_kind = choose_scale_and_page(w, h, show_label)

    if page_kind == "letter":
        paper = "letterpaper"
        margin = "1cm"
    else:
        paper = "a3paper"
        margin = "1.2cm"

    y_bottom = -(h / 2 + 2.5)
    label_line = rf"\textbf{{{title}}}\par" if show_label else ""

    return rf"""\documentclass[10pt]{{article}}
\usepackage[{paper},margin={margin}]{{geometry}}
\usepackage{{circuitikz}}
\pagestyle{{empty}}
\begin{{document}}
{label_line}
\begin{{circuitikz}}[scale={scale:.4f},transform shape]
\draw (-0.8,{y_bottom:.3f}) to[battery] (-0.8,0);
\draw (-0.8,0) -- (0,0);
{circuit_snippet}
\draw ({w:.3f}+0.4,{y_bottom:.3f}) -- (-0.8,{y_bottom:.3f});
\draw ({w:.3f}+0.4,{y_bottom:.3f}) -- ({w:.3f}+0.4, 0);
\draw ({w:.3f}+0.4,0) -- ({w:.3f}, 0);
\end{{circuitikz}}
\end{{document}}
"""

# =====================
# External tool helpers
# =====================

def run_cmd(cmd: List[str], cwd=None) -> None:
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed:\n  {' '.join(cmd)}\n\nOutput:\n{p.stdout}")

def compile_lualatex(tex_path: str, out_dir: str) -> str:
    base = os.path.splitext(os.path.basename(tex_path))[0]
    run_cmd([
        "lualatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={out_dir}",
        tex_path,
    ])
    return os.path.join(out_dir, base + ".pdf")

def pdf_to_png(pdf_path: str, png_path: str, dpi: int = 300) -> None:
    # Prefer pdftocairo if available
    try:
        run_cmd([
            "pdftocairo",
            "-png",
            "-singlefile",
            "-r", str(dpi),
            pdf_path,
            os.path.splitext(png_path)[0],
        ])
        produced = os.path.splitext(png_path)[0] + ".png"
        if produced != png_path:
            os.replace(produced, png_path)
        return
    except Exception:
        pass

    # Fallback to ImageMagick (magick)
    try:
        run_cmd([
            "magick",
            "-density", str(dpi),
            pdf_path + "[0]",
            "-quality", "100",
            png_path
        ])
        return
    except Exception as e:
        raise RuntimeError(
            "Could not convert PDF to PNG. Install poppler (pdftocairo) or ImageMagick (magick).\n"
            f"Last error: {e}"
        )

# =====================
# External tool usage
# =====================

from pathlib import Path
import tempfile

def _render_one_to_png_bytes(e: Dict[str, Any], *, dpi: int = 300, pretty: bool = True) -> bytes:
    """
    Render a single circuit tree `e` and return PNG bytes.
    Uses a TemporaryDirectory so no persistent files remain.
    """
    with tempfile.TemporaryDirectory(prefix="circuitgen_") as td:
        out_dir = Path(td)
        assets_dir = out_dir / "assets"
        pdf_dir = out_dir / "pdf_labeled"
        assets_dir.mkdir(parents=True, exist_ok=True)
        pdf_dir.mkdir(parents=True, exist_ok=True)

        topo = expr_pretty(e) if pretty else expr(e)
        d = draw(e, pretty=pretty)

        stem = "0001"
        tex_path = assets_dir / f"{stem}.tex"
        png_path = assets_dir / f"{stem}.png"
        labeled_tex_path = pdf_dir / f"{stem}.tex"

        title = f"Circuit 1: $ {topo} $"

        tex_doc_unlabeled = make_tex_document(d.tex, d.w, d.h, title=title, show_label=False)
        tex_path.write_text(tex_doc_unlabeled, encoding="utf-8")

        tex_doc_labeled = make_tex_document(d.tex, d.w, d.h, title=title, show_label=True)
        labeled_tex_path.write_text(tex_doc_labeled, encoding="utf-8")

        # labeled PDF (optional but matches your current behavior)
        _ = compile_lualatex(str(labeled_tex_path), str(pdf_dir))

        # unlabeled -> PNG
        unlabeled_pdf_path = compile_lualatex(str(tex_path), str(assets_dir))
        pdf_to_png(unlabeled_pdf_path, str(png_path), dpi=dpi)

        return png_path.read_bytes()

def generate(topology: str, *, dpi: int = 300, pretty: bool = True) -> bytes:
    """
    Public API: parse a topology string and return a rendered PNG (bytes).
    No persistent files.
    """
    e = parse_topology(topology)
    return _render_one_to_png_bytes(e, dpi=dpi, pretty=pretty)


# =====================
# Main pipeline
# =====================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=9, help="Number of resistors (when sampling)")
    ap.add_argument("--count", type=int, default=20, help="How many circuits to output (when sampling)")
    ap.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    ap.add_argument("--out", type=str, default="out", help="Output directory")
    ap.add_argument("--dpi", type=int, default=300, help="PNG DPI")
    ap.add_argument("--no-render", action="store_true", help="Only write topology+tex, skip PDF/PNG")
    ap.add_argument("--pretty", action="store_true", help="Pretty topology string + n-ary draw flattening")
    ap.add_argument(
        "--topology",
        type=str,
        default=None,
        help="Explicit topology string (uses R, +, //, parentheses). Example: '(R//(R+(R//R)))'"
    )
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    assets_dir = os.path.join(args.out, "assets")
    pdf_dir = os.path.join(args.out, "pdf_labeled")
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(pdf_dir, exist_ok=True)

    # Decide what to render
    items: List[Tuple[int, Dict[str, Any]]] = []

    if args.topology:
        e = parse_topology(args.topology)
        items = [(1, e)]
        # (Optional sanity print)
        print(f"[topology] parsed OK, resistors={count_resistors(e)}")
    else:
        all_circuits = list(gen(args.n))
        random.seed(args.seed)
        random.shuffle(all_circuits)
        selected = all_circuits[: min(args.count, len(all_circuits))]
        items = list(enumerate(selected, start=1))

    for i, e in items:
        topo = expr_pretty(e) if args.pretty else expr(e)
        d = draw(e, pretty=args.pretty)

        # if explicit topology, always write as 0001.*
        stem = "0001" if args.topology else f"{i:04d}"

        topo_path = os.path.join(assets_dir, f"{stem}_topology.txt")
        tex_path  = os.path.join(assets_dir, f"{stem}.tex")   # unlabeled tex (Overleaf-ready)
        png_path  = os.path.join(assets_dir, f"{stem}.png")   # unlabeled png
        labeled_tex_path = os.path.join(pdf_dir, f"{stem}.tex")

        # 1) topology
        with open(topo_path, "w", encoding="utf-8") as f:
            f.write(topo + "\n")

        # 2) latex standalone docs
        title = f"Circuit {i}: $ {topo} $"

        tex_doc_unlabeled = make_tex_document(d.tex, d.w, d.h, title=title, show_label=False)
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_doc_unlabeled)

        tex_doc_labeled = make_tex_document(d.tex, d.w, d.h, title=title, show_label=True)
        with open(labeled_tex_path, "w", encoding="utf-8") as f:
            f.write(tex_doc_labeled)

        # 3) render
        if not args.no_render:
            # labeled PDF (keep only PDF)
            _ = compile_lualatex(labeled_tex_path, pdf_dir)
            for ext in [".tex", ".aux", ".log"]:
                try:
                    os.remove(os.path.splitext(labeled_tex_path)[0] + ext)
                except OSError:
                    pass

            # unlabeled -> PNG (keep .tex + .png)
            unlabeled_pdf_path = compile_lualatex(tex_path, assets_dir)
            pdf_to_png(unlabeled_pdf_path, png_path, dpi=args.dpi)

            base = os.path.splitext(unlabeled_pdf_path)[0]
            for ext in [".pdf", ".aux", ".log"]:
                try:
                    os.remove(base + ext)
                except OSError:
                    pass

        print(f"[{stem}] topology={topo_path} tex={tex_path}" + (f" png={png_path}" if not args.no_render else ""))

if __name__ == "__main__":
    main()
