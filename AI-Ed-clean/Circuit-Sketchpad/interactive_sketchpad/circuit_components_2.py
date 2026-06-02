#!/usr/bin/env python3
import argparse
import os
import random
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Any, Tuple, List, Optional

# ============================================================
# Series–parallel model (leaf components can be unlabeled, valued,
# or given a symbolic label and optional explicit value).
#
# Leaf tokens supported in topology strings:
#   - Numeric prefix form (backward compatible):
#       R, 1R, 4.7R, 3/2R, 10kR, 1MR
#       C, 1C, 4.7uC, 10nC, 3/2C
#       L, 1L, 4.7mL, 10uL, 3/2L
#       SW, SW1, SW23
#
#   - Symbolic label form (new):
#       R_1
#       C_a
#       L_x
#       R_2=10            -> auto units by kind (10Ω)
#       R_2=10k           -> 10 kΩ
#       C_1=4.7u          -> 4.7 μF
#       L_3=1m            -> 1 mH
#       (units allowed too: 10Ω, 10ohm, 4.7uF, 1mH, etc.)
#
# Operators:
#   - Series:   '+'
#   - Parallel: '//'  (commutative in canonical key)
# ============================================================

_SI_MULT = {
    "": 1.0,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "M": 1e6,
    "G": 1e9,
}

_SI_CHARS = set(_SI_MULT.keys())

def E(
    kind: str,
    val: Optional[float] = None,
    *,
    si: str = "",
    raw: Optional[str] = None,
    sym: Optional[str] = None,
    explicit: bool = False,
) -> Dict[str, Any]:
    """
    Generic leaf element.
      kind: one of {"R","C","L","SW"}
      val : numeric value (numeric part, NOT multiplied by SI) or None
      si  : SI prefix ('' p n u m k M G) stored for pretty printing
      raw : original token for elements like SW (e.g., "SW17")
      sym : optional symbolic label (e.g. "R_1")
      explicit: whether val/si came from explicit '=...' syntax (vs prefix token)
    """
    return {"t": "E", "k": kind, "val": val, "si": si, "raw": raw, "sym": sym, "explicit": explicit}

def R(val: Optional[float] = None, *, si: str = "", sym: Optional[str] = None, explicit: bool = False) -> Dict[str, Any]:
    return E("R", val, si=si, sym=sym, explicit=explicit)

def C(val: Optional[float] = None, *, si: str = "", sym: Optional[str] = None, explicit: bool = False) -> Dict[str, Any]:
    return E("C", val, si=si, sym=sym, explicit=explicit)

def L(val: Optional[float] = None, *, si: str = "", sym: Optional[str] = None, explicit: bool = False) -> Dict[str, Any]:
    return E("L", val, si=si, sym=sym, explicit=explicit)

def SW(tag: str = "SW") -> Dict[str, Any]:
    return E("SW", None, raw=tag)

def S(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    return {"t": "S", "a": a, "b": b}

def P(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    return {"t": "P", "a": a, "b": b}

def _fmt_val(v: float) -> str:
    """Format numeric value for topology/labels: 1.0->'1', 4.70->'4.7'."""
    if float(v).is_integer():
        return str(int(round(v)))
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s

def expr(e: Dict[str, Any]) -> str:
    """Expression string: S -> '+', P -> '//'."""
    if e["t"] == "E":
        kind = e["k"]
        if kind == "SW":
            return e.get("raw") or "SW"

        sym = e.get("sym")
        v = e.get("val", None)
        si = e.get("si", "")
        explicit = bool(e.get("explicit", False))

        # Prefer showing symbolic syntax if present (round-trip)
        if sym:
            if v is None:
                return sym
            # explicit numeric after '='; keep SI in the pretty token
            return f"{sym}={_fmt_val(v)}{si}"
        # Otherwise, numeric-prefix token form
        return kind if v is None else f"{_fmt_val(v)}{si}{kind}"

    if e["t"] == "S":
        return f"({expr(e['a'])}+{expr(e['b'])})"
    return f"({expr(e['a'])}//{expr(e['b'])})"

def key(e: Dict[str, Any]) -> str:
    """Canonical key. Series ordered, parallel commutative. Includes element kinds + values if present."""
    if e["t"] == "E":
        kind = e["k"]
        if kind == "SW":
            return f"SW[{e.get('raw') or 'SW'}]"
        sym = e.get("sym") or ""
        v = e.get("val", None)
        si = e.get("si", "")
        if v is None:
            return f"{kind}[{sym}]" if sym else kind
        return f"{kind}[{sym}={_fmt_val(v)}{si}]" if sym else f"{kind}[{_fmt_val(v)}{si}]"

    ka, kb = key(e["a"]), key(e["b"])
    if e["t"] == "S":
        return f"S({ka},{kb})"
    # Parallel commutative
    return f"P({ka},{kb})" if ka < kb else f"P({kb},{ka})"

@lru_cache(None)
def gen(n: int) -> Tuple[Dict[str, Any], ...]:
    """Generate all unique SP trees with n resistors (unlabeled)."""
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
    """Pretty expression treating S and P as n-ary to reduce nesting."""
    if e["t"] == "E":
        kind = e["k"]
        if kind == "SW":
            return e.get("raw") or "SW"

        sym = e.get("sym")
        v = e.get("val", None)
        si = e.get("si", "")

        if sym:
            if v is None:
                return sym
            return f"{sym}={_fmt_val(v)}{si}"
        return kind if v is None else f"{_fmt_val(v)}{si}{kind}"

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

def _si_prefix_tex(si: str) -> str:
    """LaTeX for SI prefix: '' 'p' 'n' 'u' 'm' 'k' 'M' 'G'."""
    if si == "":
        return ""
    if si == "u":
        return r"\mu"
    return rf"\mathrm{{{si}}}"

def tikz_comp_label(kind: str, v: float, si: str = "") -> str:
    """
    Circuitikz label for a valued element.
      - R: Ohms (e.g., 4.7k -> '$4.7\\,\\mathrm{k}\\Omega$')
      - C: Farads (e.g., 10u -> '$10\\,\\mu\\mathrm{F}$')
      - L: Henrys (e.g., 1m -> '$1\\,\\mathrm{m}\\mathrm{H}$')
    """
    pref = _si_prefix_tex(si)
    num = _fmt_val(v)
    if kind == "R":
        if pref:
            return rf"$ {num}\,{pref}\Omega $"
        return rf"$ {num}\,\Omega $"
    if kind == "C":
        if pref:
            return rf"$ {num}\,{pref}\mathrm{{F}} $"
        return rf"$ {num}\,\mathrm{{F}} $"
    if kind == "L":
        if pref:
            return rf"$ {num}\,{pref}\mathrm{{H}} $"
        return rf"$ {num}\,\mathrm{{H}} $"
    return rf"$ {num} $"

# ======================
# Parse explicit topology
# ======================

class TopologyParseError(ValueError):
    pass

def tokenize_topology(s: str) -> List[str]:
    """
    Robust tokenizer that:
      - treats //, +, (, ) as operators even without surrounding spaces
      - supports labeled tokens like R_2=3/2 (and won't swallow the following //)
      - supports numeric-prefix tokens like 10kR, 3/2C, etc.
    """
    toks: List[str] = []
    i = 0
    n = len(s)

    def skip_ws(j: int) -> int:
        while j < n and s[j].isspace():
            j += 1
        return j

    i = skip_ws(i)
    while i < n:
        # operators first
        if s.startswith("//", i):
            toks.append("//")
            i += 2
            i = skip_ws(i)
            continue
        if s[i] in "+()":
            toks.append(s[i])
            i += 1
            i = skip_ws(i)
            continue

        # leaf: SW...
        if s.startswith("SW", i):
            j = i + 2
            while j < n and s[j].isdigit():
                j += 1
            toks.append(s[i:j])
            i = skip_ws(j)
            continue

        # leaf: labeled R/C/L forms: <KIND>[_name][=value]
        if s[i] in "RCL":
            j = i + 1
            # optional label: either _name (allow underscores) or _{name} (LaTeX-like)
            if j < n and s[j] == "_":
                j += 1
                if j < n and s[j] == "{":
                    # parse until matching '}'
                    j += 1
                    start = j
                    while j < n and s[j] != "}":
                        j += 1
                    if j >= n:
                        raise TopologyParseError("Unclosed '{' in label")
                    name = s[start:j].strip()
                    if not name or not all(ch.isalnum() or ch == "_" for ch in name):
                        raise TopologyParseError(f"Bad label name in braces: {name!r}")
                    j += 1  # consume '}'
                else:
                    # parse name after '_' allowing alnum and underscores
                    if j >= n or not (s[j].isalnum() or s[j] == "_"):
                        raise TopologyParseError(f"Bad label after '_' at position {j}")
                    while j < n and (s[j].isalnum() or s[j] == "_"):
                        j += 1

            # optional =value (value ends before an operator start: //, +, (, ))
            j = skip_ws(j)
            if j < n and s[j] == "=":
                j += 1
                j = skip_ws(j)
                if j >= n:
                    raise TopologyParseError("Missing value after '='")
                k = j
                while k < n:
                    if s.startswith("//", k) or s[k] in "+()":
                        break
                    k += 1
                val_str = s[j:k].strip()
                if val_str == "":
                    raise TopologyParseError("Empty value after '='")
                toks.append(s[i:j] + val_str)  # token includes '=' and trimmed value
                i = skip_ws(k)
                continue

            toks.append(s[i:j])
            i = skip_ws(j)
            continue

        # leaf: numeric-prefix tokens like 10kR, 3/2C, etc.
        m = re.match(r"(?:(?:\d+(?:\.\d+)?)|(?:\d+/\d+))(?:[pnumkMG])?(?:R|C|L)", s[i:])
        if m:
            tok = m.group(0)
            toks.append(tok)
            i = skip_ws(i + len(tok))
            continue

        raise TopologyParseError(f"Unexpected character at position {i}: {s}")

    return toks

def _parse_value_prefix(prefix: str) -> Tuple[float, str]:
    """
    Parse a numeric prefix that may include an SI prefix.
      - decimal/int:   "12", "4.7"
      - fraction:      "3/2"
      - SI suffix:     "10k", "4.7u", "1M", etc.

    Returns (numeric_part, si_prefix_str).
    We store the numeric part *without* applying the SI multiplier so that
    the topology string round-trips cleanly (e.g., "10kR" stays "10kR").
    """
    if prefix == "":
        raise TopologyParseError("Empty value prefix")

    si = ""
    if prefix[-1] in _SI_CHARS and prefix[-1] != "":
        if prefix[-1] in {"p", "n", "u", "m", "k", "M", "G"}:
            si = prefix[-1]
            prefix_num = prefix[:-1]
        else:
            prefix_num = prefix
    else:
        prefix_num = prefix

    if prefix_num == "":
        raise TopologyParseError(f"Missing numeric part before SI prefix {si!r}")

    if "/" in prefix_num:
        num_s, den_s = prefix_num.split("/", 1)
        num = float(num_s)
        den = float(den_s)
        if den == 0:
            raise TopologyParseError("Denominator cannot be 0 in fraction")
        base = num / den
    else:
        base = float(prefix_num)

    return base, si

_VALUE_RE = re.compile(
    r"""
    ^\s*
    (?P<num>(?:\d+(?:\.\d+)?)|(?:\d+/\d+))
    (?P<si>[pnumkMG]?)            # optional SI prefix
    \s*
    (?P<unit>(?:ohm|Ω|F|H)?)      # optional unit (case-insensitive handled later)
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE
)

def _infer_unit(kind: str) -> str:
    return {"R": "Ω", "C": "F", "L": "H"}[kind]

def _parse_explicit_value(kind: str, raw_value: str) -> Tuple[float, str]:
    """
    Parse explicit '=...' values with auto-units:
      - "10"    -> 10 Ω (if R), 10 F (if C), 10 H (if L)
      - "10k"   -> 10 kΩ (R), 10 kF (C), 10 kH (L)
      - "4.7uF" -> 4.7 u F (C)
      - "1mH"   -> 1 m H (L)
      - "10Ω" or "10ohm" -> resistor units
    Returns (numeric_part, si_prefix) in the same representation used by tikz_comp_label.
    """
    v = raw_value.strip()
    m = _VALUE_RE.match(v)
    if not m:
        raise TopologyParseError(f"Could not parse explicit value {raw_value!r}")

    num_s = m.group("num")
    si = m.group("si") or ""
    unit = (m.group("unit") or "").strip()

    # normalize unit
    unit_low = unit.lower()
    if unit_low == "ohm":
        unit_norm = "Ω"
    elif unit == "Ω":
        unit_norm = "Ω"
    elif unit_low == "f":
        unit_norm = "F"
    elif unit_low == "h":
        unit_norm = "H"
    elif unit_low == "":
        unit_norm = _infer_unit(kind)
    else:
        raise TopologyParseError(f"Unknown unit {unit!r} in value {raw_value!r}")

    # Validate unit matches kind (unless user omitted and we inferred)
    expected = _infer_unit(kind)
    if unit_norm != expected:
        raise TopologyParseError(f"Unit {unit_norm} does not match element kind {kind} (expected {expected})")

    # parse number (supports fraction)
    if "/" in num_s:
        a, b = num_s.split("/", 1)
        den = float(b)
        if den == 0:
            raise TopologyParseError("Denominator cannot be 0 in fraction")
        num = float(a) / den
    else:
        num = float(num_s)

    if si and si not in _SI_CHARS:
        raise TopologyParseError(f"Bad SI prefix {si!r} in value {raw_value!r}")

    return num, si

def parse_topology(s: str) -> Dict[str, Any]:
    """
    Grammar (left associative):
      expr   := term (('+' | '//') term)*
      term   := leaf | '(' expr ')'
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

        # Parenthesized sub-expression
        if tok == "(":
            consume("(")
            node = parse_expr()
            consume(")")
            return node

        # Switch
        if tok.startswith("SW"):
            consume(tok)
            return SW(tok)

        # Labeled form: R_1 or R_2=10k or C_a=4.7uF, etc.
        if tok and tok[0] in "RCL" and ("_" in tok or "=" in tok):
            consume(tok)
            # Normalize LaTeX label form R_{eq} -> R_eq for display
            if "{" in tok and "}" in tok:
                tok = tok.replace("{", "").replace("}", "")
            kind = tok[0]

            if "=" in tok:
                left, right = tok.split("=", 1)
                sym = left
                val_num, val_si = _parse_explicit_value(kind, right)
                return {"R": R, "C": C, "L": L}[kind](val_num, si=val_si, sym=sym, explicit=True)
            else:
                sym = tok
                return {"R": R, "C": C, "L": L}[kind](None, sym=sym, explicit=False)

        # Numeric-prefix leaf: <num><si><kind> or just <kind>
        if tok.endswith(("R", "C", "L")):
            consume(tok)
            kind = tok[-1]
            prefix = tok[:-1]
            if prefix == "":
                return {"R": R, "C": C, "L": L}[kind](None)
            val, si = _parse_value_prefix(prefix)
            return {"R": R, "C": C, "L": L}[kind](val, si=si)

        raise TopologyParseError(f"Expected element token or '(', got {tok!r}")

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

def count_elements(e: Dict[str, Any]) -> int:
    """Count leaf elements (R/C/L/SW) in the tree."""
    if e["t"] == "E":
        return 1
    return count_elements(e["a"]) + count_elements(e["b"])

# =================
# Drawing routines
# =================

@dataclass(frozen=True)
class DrawOut:
    w: float          # width in cm
    h: float          # height in cm (vertical span of subtree)
    tex: str          # circuitikz drawing commands

def latexify_symbol(sym: str) -> str:
    """
    Convert tokens like:
      R_1    -> R_{1}
      R_eq   -> R_{eq}
      R_e_q  -> R_{e_q}
    If there's no underscore, return as-is.
    """
    if "_" not in sym:
        return sym
    head, tail = sym.split("_", 1)
    # Keep the rest (may include underscores) as the subscript payload
    return f"{head}_{{{tail}}}"

def _tikz_label_for_leaf(e: Dict[str, Any]) -> Optional[str]:
    """
    Decide what label to show on the component.
      - If sym and value: show "sym = value-with-units"
      - If sym only: show sym
      - Else if numeric value: show value-with-units
      - Else: no label
    """
    kind = e["k"]
    if kind not in {"R", "C", "L"}:
        return None

    sym = e.get("sym")
    v = e.get("val", None)
    si = e.get("si", "")

    if sym:
        sym_tex = latexify_symbol(sym)
        if v is not None:
            rhs = tikz_comp_label(kind, v, si).strip("$ ").strip()
            return rf"$ {sym_tex} = {rhs} $"
        return rf"$ {sym_tex} $"
    if v is not None:
        return tikz_comp_label(kind, v, si)
    return None

def draw(e: Dict[str, Any], pretty: bool = False) -> DrawOut:
    PAD = 0.6
    series_gap = 0.4
    parallel_gap = 1.6  # used as "gap" in compact packing

    # ----------------
    # Leaf: element
    # ----------------
    if e["t"] == "E":
        kind = e["k"]
        v = e.get("val", None)
        si = e.get("si", "")
        raw = e.get("raw", None)

        label = _tikz_label_for_leaf(e)

        if kind == "R":
            if label:
                body = rf"\draw (0,0) -- (0.4,0) to[R,l={{{label}}}] (1.6,0)--(2,0);"
            else:
                body = r"\draw (0,0) -- (0.4,0) to[R] (1.6,0)--(2,0);"

        elif kind == "C":
            if label:
                body = rf"\draw (0,0) -- (0.4,0) to[C,l={{{label}}}] (1.6,0)--(2,0);"
            else:
                body = r"\draw (0,0) -- (0.4,0) to[C] (1.6,0)--(2,0);"

        elif kind == "L":
            if label:
                body = rf"\draw (0,0) -- (0.4,0) to[L,l={{{label}}}] (1.6,0)--(2,0);"
            else:
                body = r"\draw (0,0) -- (0.4,0) to[L] (1.6,0)--(2,0);"

        elif kind == "SW":
            body = r"\draw (0,0) -- (0.4,0) to[spst] (1.6,0)--(2,0);"
            if raw and raw != "SW":
                body += rf"\node[above] at (1.0,0) {{{raw}}};"
        else:
            raise ValueError(f"Unknown element kind: {kind}")

        return DrawOut(w=2.0, h=0.0, tex=body)

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
    # compact packing (no forced even spacing)
    # ---------------------------
    assert e["t"] == "P"
    kids = flatten_parallel(e) if pretty else [e["a"], e["b"]]
    drawn = [draw(k, pretty) for k in kids]

    pad = PAD if pretty else 0.0

    inner_w = max((d.w for d in drawn), default=0.0)
    w = inner_w + 2 * pad

    # Compact vertical packing
    min_branch_h = 0.9
    gap = parallel_gap

    eff_h = [max(d.h, min_branch_h) for d in drawn]
    total_h = sum(eff_h) + gap * (len(eff_h) - 1) if drawn else 0.0
    h = total_h

    centers: List[float] = []
    if drawn:
        y = total_h / 2.0 - eff_h[0] / 2.0
        centers.append(y)
        for idx in range(1, len(drawn)):
            y -= (eff_h[idx - 1] / 2.0 + gap + eff_h[idx] / 2.0)
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
    y_label = (h / 2 + 1.2)

    label_node = ""
    if show_label:
        label_node = rf"\node[anchor=west] at (-1.6,{y_label:.3f}) {{{{\textbf{{{title}}}}}}};"

    return rf"""\documentclass[10pt]{{article}}
\usepackage[{paper},margin={margin}]{{geometry}}
\usepackage{{circuitikz}}
\pagestyle{{empty}}
\begin{{document}}
\begin{{circuitikz}}[scale={scale:.4f},transform shape]
{label_node}
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

        _ = compile_lualatex(str(labeled_tex_path), str(pdf_dir))

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
        help="Explicit topology. Leaves: R/C/L + switches SW. "
             "Supports numeric prefix (10kR) and labels (R_2=10k). "
             "Example: '(R_1//(R_2=10k+(C_1=4.7u//SW1)))'"
    )
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    assets_dir = os.path.join(args.out, "assets")
    pdf_dir = os.path.join(args.out, "pdf_labeled")
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(pdf_dir, exist_ok=True)

    items: List[Tuple[int, Dict[str, Any]]] = []

    if args.topology:
        e = parse_topology(args.topology)
        items = [(1, e)]
        print(f"[topology] parsed OK, elements={count_elements(e)}")
    else:
        all_circuits = list(gen(args.n))
        random.seed(args.seed)
        random.shuffle(all_circuits)
        selected = all_circuits[: min(args.count, len(all_circuits))]
        items = list(enumerate(selected, start=1))

    for i, e in items:
        topo = expr_pretty(e) if args.pretty else expr(e)
        d = draw(e, pretty=args.pretty)

        stem = "0001" if args.topology else f"{i:04d}"

        topo_path = os.path.join(assets_dir, f"{stem}_topology.txt")
        tex_path  = os.path.join(assets_dir, f"{stem}.tex")
        png_path  = os.path.join(assets_dir, f"{stem}.png")
        labeled_tex_path = os.path.join(pdf_dir, f"{stem}.tex")

        with open(topo_path, "w", encoding="utf-8") as f:
            f.write(topo + "\n")

        title = f"Circuit {i}: $ {topo} $"

        tex_doc_unlabeled = make_tex_document(d.tex, d.w, d.h, title=title, show_label=False)
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_doc_unlabeled)

        tex_doc_labeled = make_tex_document(d.tex, d.w, d.h, title=title, show_label=True)
        with open(labeled_tex_path, "w", encoding="utf-8") as f:
            f.write(tex_doc_labeled)

        if not args.no_render:
            _ = compile_lualatex(labeled_tex_path, pdf_dir)
            for ext in [".tex", ".aux", ".log"]:
                try:
                    os.remove(os.path.splitext(labeled_tex_path)[0] + ext)
                except OSError:
                    pass

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