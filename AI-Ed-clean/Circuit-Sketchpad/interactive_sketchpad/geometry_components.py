import argparse
import os
import random
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Any, Tuple, List, Optional
from pathlib import Path

def run_cmd(cmd: List[str], cwd=None) -> None:
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed:\n  {' '.join(cmd)}\n\nOutput:\n{p.stdout}")

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
    
def parse_topology_to_dict(topology: str) -> dict:
    #Regex looking for a substring of the format "Vertex [Label]:([x coordinate],[y coordinate])" with optional whitespace
    vertices_regex = re.compile(r"Vertex \s+ [A-Z] \s* : \s* \( [^,]+ \s* , \s* .+ \s* \) ", re.IGNORECASE)
    

def generate(topology: str, *, dpi: int = 300, pretty: bool = True) -> bytes:
    pdf_to_png("tikzdraw.pdf", "tikzdraw.png", dpi = dpi)
    pngpath = Path() / "tikzdraw.png"
    return pngpath.read_bytes()