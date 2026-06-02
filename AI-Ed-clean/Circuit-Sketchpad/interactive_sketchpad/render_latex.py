#!/usr/bin/env python3
"""
latex_imagegen.py

Standalone "generate()" API like your circuit code:
  - generate(latex, dpi=300, snippet=False) -> PNG bytes

CLI examples:
  ./latex_imagegen.py --tex-file input.tex --out out.png
  ./latex_imagegen.py --stdin --snippet --out out.png
  ./latex_imagegen.py --tex "\\Huge Hello!" --snippet --out hello.png

Requires:
  - lualatex
  - and either pdftocairo (preferred) or ImageMagick 'magick'
"""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional


from PIL import Image
import io


# =====================
# External tool helpers
# =====================

def run_cmd(cmd: List[str], cwd: Optional[str] = None) -> str:
    """Run a command, raise on failure, return combined stdout/stderr."""
    p = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if p.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            f"  {' '.join(cmd)}\n\n"
            f"Output:\n{p.stdout}"
        )
    return p.stdout


def compile_lualatex(tex_path: str, out_dir: str) -> str:
    """Compile a .tex file with lualatex; return produced PDF path."""
    base = os.path.splitext(os.path.basename(tex_path))[0]
    run_cmd(
        [
            "lualatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-output-directory={out_dir}",
            tex_path,
        ]
    )
    return os.path.join(out_dir, base + ".pdf")


def pdf_to_png(pdf_path: str, png_path: str, dpi: int = 300) -> None:
    """
    Convert first page of PDF to PNG.
    Prefers pdftocairo; falls back to ImageMagick `magick`.
    """
    png_path = str(png_path)

    # Prefer pdftocairo if available
    try:
        run_cmd(
            [
                "pdftocairo",
                "-png",
                "-singlefile",
                "-r",
                str(dpi),
                pdf_path,
                os.path.splitext(png_path)[0],
            ]
        )
        produced = os.path.splitext(png_path)[0] + ".png"
        if produced != png_path:
            os.replace(produced, png_path)
        return
    except Exception:
        pass

    # Fallback to ImageMagick (magick)
    try:
        run_cmd(
            [
                "magick",
                "-density",
                str(dpi),
                pdf_path + "[0]",
                "-quality",
                "100",
                png_path,
            ]
        )
        return
    except Exception as e:
        raise RuntimeError(
            "Could not convert PDF to PNG. Install poppler (pdftocairo) or ImageMagick (magick).\n"
            f"Last error: {e}"
        )


# =========================
# LaTeX wrapping (optional)
# =========================

def _wrap_snippet_as_document(snippet: str) -> str:
    """
    Wrap body content into a minimal document.
    (Useful if input is not a full \\documentclass... file.)
    """
    return r"""\documentclass[border=2pt]{standalone}
\usepackage{amsmath,amssymb}
\begin{document}
""" + snippet + r"""
\end{document}
"""


# ==========================
# Public API: generate() API
# ==========================

def generate(latex: str, *, dpi: int = 300, snippet: bool = False) -> bytes:
    """
    Public API (like your circuit generator):
      - latex: full LaTeX document, unless snippet=True
      - dpi: PNG rasterization DPI
      - snippet: if True, wrap latex as document body

    Returns:
      PNG bytes (no persistent files).
    """
    tex_source = _wrap_snippet_as_document(latex) if snippet else latex

    with tempfile.TemporaryDirectory(prefix="latexgen_") as td:
        td_path = Path(td)
        build_dir = td_path / "build"
        build_dir.mkdir(parents=True, exist_ok=True)

        tex_path = td_path / "doc.tex"
        tex_path.write_text(tex_source, encoding="utf-8")

        pdf_path = compile_lualatex(str(tex_path), str(build_dir))

        png_path = td_path / "out.png"
        pdf_to_png(pdf_path, str(png_path), dpi=dpi)

        return png_path.read_bytes()


# =================
# Main CLI pipeline
# =================

def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a PNG image from LaTeX. Public API is generate().")

    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--tex-file", type=str, help="Path to .tex (full document unless --snippet).")
    src.add_argument("--tex", type=str, help="LaTeX string (full document unless --snippet).")
    src.add_argument("--stdin", action="store_true", help="Read LaTeX from stdin.")

    ap.add_argument("--out", type=str, required=True, help="Output PNG file path.")
    ap.add_argument("--dpi", type=int, default=300, help="PNG DPI (default: 300).")
    ap.add_argument("--snippet", action="store_true", help="Treat input as snippet/body and wrap into a document.")

    args = ap.parse_args()

    if args.tex_file:
        latex = Path(args.tex_file).read_text(encoding="utf-8")
    elif args.tex is not None:
        latex = args.tex
    else:
        latex = os.sys.stdin.read()

    png_bytes = generate(latex, dpi=args.dpi, snippet=args.snippet)
    Path(args.out).write_bytes(png_bytes)
    print(f"Wrote: {args.out}")
    return 0



if __name__ == "__main__":
    # main()

    latex = """
    \\documentclass[12pt]{amsart}
%\\addtolength{\\oddsidemargin}{-0 in}
%\\addtolength{\\evensidemargin}{-0 in}
%\\addtolength{\\textwidth}{0.5in} \\addtolength{\\textheight}{1in}
%\\addtolength{\\topmargin}{-0.25in}
%\\addtolength{\\topmargin}{-0.5in}
\\newcommand{\\blank}{\\makebox[1in]{\\hrulefill}}
\\newcommand{\\ds}{\\displaystyle}
\\newcommand{\\vs}{\\vspace}
\\newcommand{\\be}{\\begin{enumerate}}
\\newcommand{\\ee}{\\end{enumerate}}
\\newcommand{\\bd}{\\begin{description}}
\\newcommand{\\ed}{\\end{description}}
\\newcommand{\\bi}{\\begin{itemize}}
\\newcommand{\\ei}{\\end{itemize}}
\\usepackage{pgf,tikz}
\\usepackage{amsmath}

\\usepackage{graphicx,tipa}% http://ctan.org/pkg/{graphicx,tipa}
\\newcommand{\\arc}[1]{{%
  \\setbox9=\\hbox{#1}%
  \\ooalign{\\resizebox{\\wd9}{\\height}{\\texttoptiebar{\\phantom{A}}}\\cr#1}}}
  
\\usetikzlibrary{calc,intersections,angles,quotes, patterns, decorations.pathmorphing,shapes.geometric}
\\usepackage{tkz-euclide} % For angle marks

\\begin{document}
\\noindent {\\sl Tag: Circle, Lune, Area }
\\medskip

The shaded region is called a lune. Given that $CD=2\\sqrt{2}$, $AB=2$, and that $AB$ and $CD$ are diameters of the respective semicircles, find the area of the lune.

\\medskip

\\begin{tikzpicture}[scale=2]
% extracted numbers from the problem
\\pgfmathsetmacro{\\CD}{2*sqrt(2)}
\\pgfmathsetmacro{\\AB}{2}

% Derived values
\\pgfmathsetmacro{\\R}{\\CD/2} % large semicircle radius
\\pgfmathsetmacro{\\r}{\\AB/2} % small semicircle radius
\\pgfmathsetmacro{\\h}{sqrt(max(0,(\\R)^2 - (\\r)^2))} % height offset to keep shape consistent

% Coordinates for large semicircle
\\coordinate (C) at (0,0);
\\coordinate (D) at (\\CD,0);
\\coordinate (O) at ($(C)!0.5!(D)$);

% Small semicircle (centered above O)
\\coordinate (A) at ($(O)+(-\\r,\\h)$);
\\coordinate (B) at ($(O)+(\\r,\\h)$);
\\coordinate (S) at ($(A)!0.5!(B)$); % center of small semicircle (not labeled)

% Draw semicircles
\\draw[thick] (C)--(D);
\\draw[thick] (C) arc[start angle=180,end angle=0,radius=\\R];
\\draw[thick] (A) arc[start angle=180,end angle=0,radius=\\r];
\\draw[thick] (A)--(B);

% Shade small semicircle, then subtract the large semicircle area to show the lune
\\begin{scope}
\\clip (S) circle (\\r);
\\fill[blue!30] (A) arc[start angle=180,end angle=0,radius=\\r] -- (A) -- (B) -- cycle;
\\end{scope}

% White-out below large semicircle to make the lune shape clean
\\begin{scope}
\\fill[white] (C) arc[start angle=180,end angle=0,radius=\\R] -- (C) -- (D) -- cycle;
\\end{scope}

% Redraw borders
\\draw[thick] (A) arc[start angle=180,end angle=0,radius=\\r];
\\draw[thick] (C) arc[start angle=180,end angle=0,radius=\\R];
\\draw[thick] (A)--(B);

% Label points
\\foreach \\p/\\pos in {A/left,B/right,C/below,D/below,O/below}
\\fill (\\p) circle (1pt) node[\\pos] {\\p};
\\end{tikzpicture}


\\bigskip
\\noindent{\\sl Conversations:}
\\medskip

Q: Let's name the area of the shaded piece $S_1$, and the area under the lune but above the secant line $AB$ $S_2$. How can you find $S_1$ from $S_2$? 

A: $S_1$ is the area of the semicircle of the smaller circle subtracting $S_2$.

Q: Yes indeed. Now we are in the larger circle. Please connect $AO$ and $BO$. Notice $S_2$ equals the circular segment $O\\arc{AB}$ subtracting $[\\triangle OAB]$. Draw a height $OE$ from $O$ to $AB$. What else can you say about $OE$ other than $OE\\perp AB$?

A: $AE=EB$.

Q: Absolutely! What is $OB$, and then $OE$?

A: $OB=OD=\\sqrt{2}$, and $OE=(\\sqrt{2}\\ )^2-1=1$.

Q: Great! Not only have all the information need to find the area of $\\triangle OAB$, but also $\\angle AOB$. What's its measure?

A: $\\triangle OEB$ is an isosceles right triangle, $\\angle *OE=45^\\circ$ and $\\angle AOB=90^\\circ.$

Q: Very nice! Now please find $S_2$, then $S_1.$

A: $S_2=\\frac{1}{4} \\times \\pi\\times (\\sqrt{2})^2=\\frac{\\pi}{2}-1,$ and $S_1=\\frac{1}{2}\\times \\pi-S_2=1.$

Q: Excellent! That's all for this problem. See you later.





\\end{document}
    """

    png_bytes = generate(latex)

    img = Image.open(io.BytesIO(png_bytes))
    img.show()

