"""Circuit figures: schematics on a grid and x–y plots.

A schematic is a list of elements on a grid (y grows downward, 0.5 steps).
Two-terminal parts run between two grid points; transistors and op amps sit
at a point and expose fixed terminals, so wires can be checked for loose
ends before anything is drawn:

    nmos / npn at (x, y):  top (drain/collector) (x+1, y-1)
    pmos / pnp at (x, y):  top (source/emitter)  (x+1, y-1)
                           control (gate/base)   (x-1, y)
                           bottom                (x+1, y+1)
    opamp at (x, y):       −  (x-1, y-0.5),  +  (x-1, y+0.5),  out (x+1, y)

`mirror` flips transistors and op amps left to right; for two-terminal parts,
ports and labels it moves the label to the other side. Labels, arrows and
boxes are annotations: they connect to nothing and may sit off the grid.
"""

from __future__ import annotations

import html
import math
import re

TWO_TERMINAL = ("resistor", "capacitor", "isource", "vsource", "vccs")
TRANSISTORS = ("nmos", "pmos", "npn", "pnp")
POINT_PARTS = ("ground", "vdd", "port", "dot")
ANNOTATIONS = ("label", "arrow", "box")
GRID_MAX = 40
U = 34  # pixels per grid unit

Point = tuple[float, float]


def _pt(p) -> Point:
    return (float(p[0]), float(p[1]))


def terminals(el: dict) -> list[Point]:
    """Connection points of an element (empty for annotations)."""
    t, pts = el["type"], [_pt(p) for p in el["points"]]
    if not pts:
        return []
    if t == "wire":
        return pts
    if t in TWO_TERMINAL:
        return pts[:2]
    x, y = pts[0]
    s = -1 if el["mirror"] else 1
    if t in TRANSISTORS:
        return [(x + s, y - 1), (x - s, y), (x + s, y + 1)]
    if t == "opamp":
        return [(x - s, y - 0.5), (x - s, y + 0.5), (x + s, y)]
    if t in POINT_PARTS:
        return [pts[0]]
    return []


def _on_segment(p: Point, a: Point, b: Point) -> bool:
    if a[0] == b[0] == p[0]:
        return min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    if a[1] == b[1] == p[1]:
        return min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
    return False


def _touches(p: Point, other: dict) -> bool:
    if p in terminals(other):
        return True
    if other["type"] == "wire":
        pts = [_pt(q) for q in other["points"]]
        return any(_on_segment(p, a, b) for a, b in zip(pts, pts[1:]))
    return False


def schematic_issues(figure: dict, where: str) -> list[str]:
    issues: list[str] = []
    elements = figure["elements"]
    if not elements:
        return [f"{where}: schematic figure needs elements"]
    expected = {**{t: 2 for t in TWO_TERMINAL}, **{t: 1 for t in TRANSISTORS + POINT_PARTS + ("opamp", "label")},
                "arrow": 2, "box": 2}
    shape_ok = []
    for i, el in enumerate(elements):
        at = f"{where}.elements[{i}:{el['type']}]"
        pts = el["points"]
        ok = True
        if any(len(p) != 2 for p in pts):
            issues.append(f"{at}: every point is [x, y]")
            shape_ok.append(False)
            continue
        t = el["type"]
        for x, y in pts:
            # Connection points sit on the 0.5 grid; annotations may be placed freely.
            off_grid = t not in ANNOTATIONS and ((x * 2) % 1 or (y * 2) % 1)
            if not (0 <= x <= GRID_MAX and 0 <= y <= GRID_MAX) or off_grid:
                issues.append(f"{at}: point ({x}, {y}) must lie {'on the 0.5 grid ' if off_grid else ''}within 0..{GRID_MAX}")
                ok = False
        if t == "wire":
            if len(pts) < 2:
                issues.append(f"{at}: a wire needs at least two points")
                ok = False
            for a, b in zip(pts, pts[1:]):
                if (a[0] != b[0] and a[1] != b[1]) or a == b:
                    issues.append(f"{at}: wire segment {a}->{b} must be horizontal or vertical and non-empty")
        elif len(pts) != expected[t]:
            issues.append(f"{at}: needs exactly {expected[t]} point(s), got {len(pts)}")
            ok = False
        elif t in TWO_TERMINAL:
            (x1, y1), (x2, y2) = pts
            if (x1 != x2 and y1 != y2) or math.hypot(x2 - x1, y2 - y1) < 1:
                issues.append(f"{at}: must run horizontally or vertically over at least 1 grid unit")
        elif t == "box" and (pts[0][0] == pts[1][0] or pts[0][1] == pts[1][1]):
            issues.append(f"{at}: box corners must span an area")
        shape_ok.append(ok)
    if issues:
        return issues
    # Loose ends: every terminal must meet another element's terminal or lie on a wire.
    for i, el in enumerate(elements):
        own = terminals(el)
        check = [own[0], own[-1]] if el["type"] == "wire" else own
        for p in check:
            if not any(_touches(p, other) for j, other in enumerate(elements) if j != i):
                issues.append(f"{where}.elements[{i}:{el['type']}{' ' + el['label'] if el['label'] else ''}]: "
                              f"terminal at ({p[0]:g}, {p[1]:g}) is not connected")
    return issues


def plot_issues(figure: dict, where: str) -> list[str]:
    issues = []
    if not figure["series"]:
        issues.append(f"{where}: plot figure needs at least one series")
    for i, s in enumerate(figure["series"]):
        if len(s["xs"]) != len(s["ys"]) or len(s["xs"]) < 2:
            issues.append(f"{where}.series[{i}]: xs and ys need the same length (at least 2)")
        if any(not math.isfinite(v) for v in s["xs"] + s["ys"]):
            issues.append(f"{where}.series[{i}]: values must be finite")
    return issues


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------

_SYMBOLS = {
    "\\parallel": "‖", "\\infty": "∞", "\\lambda": "λ", "\\approx": "≈", "\\Omega": "Ω", "\\Delta": "Δ",
    "\\alpha": "α", "\\beta": "β", "\\gamma": "γ", "\\theta": "θ", "\\cdot": "·", "\\times": "×",
    "\\mu": "μ", "\\pi": "π", "\\pm": "±", "\\ll": "≪", "\\gg": "≫", "\\to": "→", "\\leftarrow": "←",
    "\\rightarrow": "→", "\\uparrow": "↑", "\\downarrow": "↓", "\\|": "‖", "\\,": " ", "\\;": " ", "\\ ": " ",
}
_TEXT_CMD = re.compile(r"\\(?:text|mathrm|mathit|mathbf|rm)\{([^{}]*)\}")


def svg_text(label: str) -> str:
    """A label in light TeX notation ('g_{m1} v_{\\pi}', 'R_{out}') as SVG tspans."""
    s = _TEXT_CMD.sub(r"\1", label.replace("$", ""))
    for cmd in sorted(_SYMBOLS, key=len, reverse=True):
        s = s.replace(cmd, _SYMBOLS[cmd])
    out, i, base = [], 0, 0.0
    plain = []

    def flush():
        if plain:
            out.append(html.escape("".join(plain)))
            plain.clear()

    while i < len(s):
        ch = s[i]
        if ch in "_^" and i + 1 < len(s):
            flush()
            if s[i + 1] == "{":
                depth, j = 1, i + 2
                while j < len(s) and depth:
                    depth += {"{": 1, "}": -1}.get(s[j], 0)
                    j += 1
                group = s[i + 2:j - 1]
                i = j
            else:
                group = s[i + 1]
                i += 2
            shift = 0.32 if ch == "_" else -0.45
            group = group.replace("{", "").replace("}", "")
            out.append(f'<tspan dy="{shift - base:.2f}em" font-size="78%">{html.escape(group)}</tspan>')
            base = shift
            continue
        if base:
            # Return to the baseline (the em of the next tspan is the full size again).
            flush()
            out.append(f'<tspan dy="{-base * 0.78:.2f}em">')
            j = i
            while j < len(s) and s[j] not in "_^":
                j += 1
            out.append(html.escape(s[i:j].replace("{", "").replace("}", "")) + "</tspan>")
            base = 0.0
            i = j
            continue
        if ch not in "{}":
            plain.append(ch)
        i += 1
    flush()
    return "".join(out)


def _label_width(label: str) -> float:
    """Rough width of a label in grid units (for the drawing's bounds)."""
    s = _TEXT_CMD.sub(r"\1", label.replace("$", ""))
    for cmd in _SYMBOLS:
        s = s.replace(cmd, "x")
    small = sum(len(m) for m in re.findall(r"[_^](\{[^}]*\}|.)", s))
    full = len(re.sub(r"[_^](\{[^}]*\}|.)|[{}]", "", s))
    return (full * 0.5 + small * 0.4) * 16 / U


_SUB = str.maketrans("0123456789+-=()aehijklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ")


def tex_to_plain(label: str) -> str:
    """Light TeX ('$V_{in}$ → $2V_T$') as plain Unicode text, for places math cannot be typeset (flow arrows)."""
    s = _TEXT_CMD.sub(r"\1", label.replace("$", ""))
    for cmd in sorted(_SYMBOLS, key=len, reverse=True):
        s = s.replace(cmd, _SYMBOLS[cmd])
    s = re.sub(r"\\(?:mathrm|left|right|,|;|!)", "", s)

    def sub(m: re.Match) -> str:
        group = m.group(1) or m.group(2)
        return group.translate(_SUB) if all(c in "0123456789+-=()aehijklmnoprstuvx" for c in group) else group

    s = re.sub(r"_\{([^{}]*)\}|_(.)", sub, s)
    s = re.sub(r"\^\{([^{}]*)\}|\^(.)", lambda m: m.group(1) or m.group(2), s)
    return s.replace("{", "").replace("}", "").replace("\\", "")


class _Pen:
    def __init__(self):
        self.parts: list[str] = []
        self.xs: list[float] = []
        self.ys: list[float] = []

    def X(self, x: float) -> float:
        self.xs.append(x)
        return x * U

    def Y(self, y: float) -> float:
        self.ys.append(y)
        return y * U

    def line(self, pts: list[Point], cls: str, extra: str = "") -> None:
        d = " ".join(f"{self.X(x):.1f},{self.Y(y):.1f}" for x, y in pts)
        self.parts.append(f'<polyline class="{cls}" points="{d}"{extra}/>')

    def poly(self, pts: list[Point], cls: str) -> None:
        d = " ".join(f"{self.X(x):.1f},{self.Y(y):.1f}" for x, y in pts)
        self.parts.append(f'<polygon class="{cls}" points="{d}"/>')

    def circle(self, c: Point, r: float, cls: str) -> None:
        self.parts.append(f'<circle class="{cls}" cx="{self.X(c[0]):.1f}" cy="{self.Y(c[1]):.1f}" r="{r * U:.1f}"/>')

    def text(self, p: Point, label: str, anchor: str = "start", cls: str = "t") -> None:
        if not label:
            return
        w = _label_width(label)
        left = {"start": 0, "middle": -w / 2, "end": -w}[anchor]
        self.xs += [p[0] + left, p[0] + left + w]
        self.ys += [p[1] - 0.45, p[1] + 0.2]
        self.parts.append(
            f'<text class="{cls}" x="{self.X(p[0]):.1f}" y="{self.Y(p[1]):.1f}" text-anchor="{anchor}">{svg_text(label)}</text>'
        )

    def head(self, tail: Point, tip: Point, cls: str, size: float = 0.2) -> None:
        dx, dy = tip[0] - tail[0], tip[1] - tail[1]
        n = math.hypot(dx, dy) or 1
        ux, uy = dx / n, dy / n
        bx, by = tip[0] - ux * size, tip[1] - uy * size
        self.poly([tip, (bx - uy * size * 0.5, by + ux * size * 0.5), (bx + uy * size * 0.5, by - ux * size * 0.5)], cls)


def _two_terminal(pen: _Pen, el: dict, cls: str, fill: str) -> None:
    (x1, y1), (x2, y2) = (_pt(p) for p in el["points"])
    length = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    nx, ny = -uy, ux  # normal
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    t = el["type"]
    half = {"resistor": 0.42, "capacitor": 0.08, "isource": 0.32, "vsource": 0.32, "vccs": 0.36}[t]
    a = (mx - ux * half, my - uy * half)
    b = (mx + ux * half, my + uy * half)
    pen.line([(x1, y1), a], cls)
    pen.line([b, (x2, y2)], cls)
    if t == "resistor":
        zig = [a]
        for k in range(1, 7):
            f = -half + k * (2 * half) / 7
            side = 0.17 if k % 2 else -0.17
            zig.append((mx + ux * f + nx * side, my + uy * f + ny * side))
        zig.append(b)
        pen.line(zig, cls)
    elif t == "capacitor":
        for p in (a, b):
            pen.line([(p[0] - nx * 0.3, p[1] - ny * 0.3), (p[0] + nx * 0.3, p[1] + ny * 0.3)], cls)
    elif t in ("isource", "vsource"):
        pen.circle((mx, my), 0.32, f"{cls} {fill}")
        if t == "isource":
            tail, tip = (mx - ux * 0.2, my - uy * 0.2), (mx + ux * 0.2, my + uy * 0.2)
            pen.line([tail, tip], cls)
            pen.head(tail, tip, f"{cls} solid", 0.14)
        else:
            pen.text((mx - ux * 0.14 - 0.02, my - uy * 0.14 + 0.07), "+", "middle", "t sign")
            pen.text((mx + ux * 0.16 - 0.02, my + uy * 0.16 + 0.07), "−", "middle", "t sign")
    elif t == "vccs":
        d = 0.36
        pen.poly([(mx + ux * d, my + uy * d), (mx + nx * d, my + ny * d), (mx - ux * d, my - uy * d), (mx - nx * d, my - ny * d)],
                 f"{cls} {fill}")
        tail, tip = (mx - ux * 0.2, my - uy * 0.2), (mx + ux * 0.2, my + uy * 0.2)
        pen.line([tail, tip], cls)
        pen.head(tail, tip, f"{cls} solid", 0.13)
    side = -1 if el["mirror"] else 1
    if x1 == x2:  # vertical: label to the right (left if mirrored)
        pen.text((mx + side * (half + 0.2 if t in ("isource", "vsource", "vccs") else 0.38), my + 0.13), el["label"],
                 "start" if side > 0 else "end", f"t {cls}")
    else:  # horizontal: label above (below if mirrored)
        pen.text((mx, my - 0.42 if side > 0 else my + 0.62), el["label"], "middle", f"t {cls}")


def _transistor(pen: _Pen, el: dict, cls: str) -> None:
    x, y = _pt(el["points"][0])
    s = -1 if el["mirror"] else 1
    t = el["type"]
    if t in ("nmos", "pmos"):
        pen.line([(x - s, y), (x - 0.22 * s, y)], cls)
        pen.line([(x - 0.22 * s, y - 0.42), (x - 0.22 * s, y + 0.42)], cls)
        pen.line([(x, y - 0.5), (x, y + 0.5)], f"{cls} thick")
        pen.line([(x, y - 0.35), (x + s, y - 0.35), (x + s, y - 1)], cls)
        pen.line([(x, y + 0.35), (x + s, y + 0.35), (x + s, y + 1)], cls)
        if t == "nmos":  # arrow on the source, pointing out of the channel
            pen.head((x + 0.2 * s, y + 0.35), (x + 0.62 * s, y + 0.35), f"{cls} solid", 0.2)
        else:  # pmos: source on top, arrow pointing into the channel
            pen.head((x + 0.8 * s, y - 0.35), (x + 0.28 * s, y - 0.35), f"{cls} solid", 0.2)
    else:
        pen.line([(x - s, y), (x, y)], cls)
        pen.line([(x, y - 0.42), (x, y + 0.42)], f"{cls} thick")
        top = [(x, y - 0.18), (x + s, y - 0.6), (x + s, y - 1)]
        bottom = [(x, y + 0.18), (x + s, y + 0.6), (x + s, y + 1)]
        pen.line(top, cls)
        pen.line(bottom, cls)
        if t == "npn":  # emitter at the bottom, arrow pointing away from the base
            a, b = bottom[0], bottom[1]
            pen.head(a, (a[0] + (b[0] - a[0]) * 0.85, a[1] + (b[1] - a[1]) * 0.85), f"{cls} solid", 0.2)
        else:  # pnp: emitter on top, arrow pointing toward the base
            a, b = top[1], top[0]
            pen.head(a, (a[0] + (b[0] - a[0]) * 0.75, a[1] + (b[1] - a[1]) * 0.75), f"{cls} solid", 0.2)
    pen.text((x + s * 1.18, y + 0.14), el["label"], "start" if s > 0 else "end", f"t {cls}")


def _opamp(pen: _Pen, el: dict, cls: str, fill: str) -> None:
    x, y = _pt(el["points"][0])
    s = -1 if el["mirror"] else 1
    pen.poly([(x - s, y - 1), (x - s, y + 1), (x + s, y)], f"{cls} {fill}")
    pen.text((x - 0.72 * s, y - 0.32), "−", "middle", "t sign")
    pen.text((x - 0.72 * s, y + 0.68), "+", "middle", "t sign")
    pen.text((x - 0.1 * s, y + 0.14), el["label"], "middle", f"t {cls}")


def schematic_svg(figure: dict) -> str:
    elements = figure["elements"]
    pen = _Pen()
    for el in elements:
        role = el["role"]
        cls = f"w r-{role}"
        fill = "bg"
        t = el["type"]
        if t == "wire":
            pen.line([_pt(p) for p in el["points"]], cls)
            if el["label"]:
                (x, y) = _pt(el["points"][-1])
                pen.text((x + 0.15, y - 0.15), el["label"], "start", f"t {cls}")
        elif t in TWO_TERMINAL:
            _two_terminal(pen, el, cls, fill)
        elif t in TRANSISTORS:
            _transistor(pen, el, cls)
        elif t == "opamp":
            _opamp(pen, el, cls, fill)
        elif t == "ground":
            x, y = _pt(el["points"][0])
            pen.line([(x, y), (x, y + 0.3)], cls)
            for k, w in enumerate((0.3, 0.19, 0.08)):
                pen.line([(x - w, y + 0.3 + k * 0.12), (x + w, y + 0.3 + k * 0.12)], cls)
        elif t == "vdd":
            x, y = _pt(el["points"][0])
            pen.line([(x - 0.35, y), (x + 0.35, y)], f"{cls} thick")
            pen.text((x, y - 0.22), el["label"] or "V_{DD}", "middle", f"t {cls}")
        elif t == "port":
            x, y = _pt(el["points"][0])
            pen.circle((x, y), 0.1, f"{cls} bg")
            if el["mirror"]:
                pen.text((x + 0.22, y + 0.13), el["label"], "start", f"t {cls}")
            else:
                pen.text((x - 0.22, y + 0.13), el["label"], "end", f"t {cls}")
        elif t == "dot":
            pen.circle(_pt(el["points"][0]), 0.08, f"{cls} solid")
        elif t == "label":
            pen.text(_pt(el["points"][0]), el["label"], "end" if el["mirror"] else "start", f"t {cls}")
        elif t == "arrow":
            tail, tip = (_pt(p) for p in el["points"])
            pen.line([tail, tip], cls)
            pen.head(tail, tip, f"{cls} solid", 0.2)
            if tail[0] == tip[0]:
                pen.text((tail[0] + 0.15, tail[1] + (0.05 if tip[1] > tail[1] else 0.3)), el["label"], "start", f"t {cls}")
            else:
                pen.text((tail[0], tail[1] - 0.18), el["label"], "middle", f"t {cls}")
        elif t == "box":
            (x1, y1), (x2, y2) = (_pt(p) for p in el["points"])
            pen.line([(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)], f"{cls} dash")
            pen.text((min(x1, x2) + 0.12, min(y1, y2) + 0.38), el["label"], "start", f"t small {cls}")
    title = html.escape(figure["title"] or "회로도", quote=True)
    pad = 0.35
    x0, y0 = (min(pen.xs) - pad) * U, (min(pen.ys) - pad) * U
    width, height = (max(pen.xs) - min(pen.xs) + 2 * pad) * U, (max(pen.ys) - min(pen.ys) + 2 * pad) * U
    return (
        f'<svg class="sch" viewBox="{x0:.0f} {y0:.0f} {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}" '
        f'role="img" aria-label="{title}">{"".join(pen.parts)}</svg>'
    )


def _nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=raw)
    start = math.ceil(lo / step) * step
    ticks = []
    v = start
    while v <= hi + 1e-9 * span:
        ticks.append(round(v, 10))
        v += step
    return ticks


def _tick_label(v: float) -> str:
    if abs(v) < 1e-12:
        return "0"
    if abs(v) >= 1000 or abs(v) < 0.01:
        return f"{v:.1e}".replace("e+0", "e").replace("e-0", "e-")
    return f"{v:g}".replace("-", "−")


def plot_svg(figure: dict) -> str:
    series = figure["series"]
    xs = [v for s in series for v in s["xs"]] + [m["x"] for m in figure["marks"]]
    ys = [v for s in series for v in s["ys"]] + [m["y"] for m in figure["marks"]]
    # A plot made only of two-point series is a vector diagram: arrows from tail to tip,
    # the origin in view and the same scale on both axes, so right angles look right.
    vector = bool(series) and all(len(s["xs"]) == 2 for s in series)
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    w, h, left, right, top, bottom = 400, 250, 46, 16, 14, 38
    if vector:
        h = 300
        x0, x1, y0, y1 = min(x0, 0), max(x1, 0), min(y0, 0), max(y1, 0)
        pad = 0.12 * max(x1 - x0, y1 - y0, 1e-9)
        x0, x1, y0, y1 = x0 - pad, x1 + pad, y0 - pad, y1 + pad
        pw, ph = w - left - right, h - top - bottom
        scale = min(pw / (x1 - x0), ph / (y1 - y0))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        x0, x1 = cx - pw / scale / 2, cx + pw / scale / 2
        y0, y1 = cy - ph / scale / 2, cy + ph / scale / 2
    else:
        if y1 - y0 < 1e-12:
            y0, y1 = y0 - 1, y1 + 1
        pad = (y1 - y0) * 0.08
        y0, y1 = y0 - pad, y1 + pad

    def X(v: float) -> float:
        return left + (v - x0) / (x1 - x0 or 1) * (w - left - right)

    def Y(v: float) -> float:
        return h - bottom - (v - y0) / (y1 - y0) * (h - top - bottom)

    parts = [f'<svg class="plot" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
             f'aria-label="{html.escape(figure["title"] or "그래프", quote=True)}">']
    for t in _nice_ticks(x0, x1):
        parts.append(f'<line x1="{X(t):.1f}" y1="{top}" x2="{X(t):.1f}" y2="{h - bottom}" style="stroke:var(--rule);stroke-width:1"/>')
        parts.append(f'<text x="{X(t):.1f}" y="{h - bottom + 14}" text-anchor="middle">{_tick_label(t)}</text>')
    for t in _nice_ticks(y0, y1):
        parts.append(f'<line x1="{left}" y1="{Y(t):.1f}" x2="{w - right}" y2="{Y(t):.1f}" style="stroke:var(--rule);stroke-width:1"/>')
        parts.append(f'<text x="{left - 5}" y="{Y(t) + 4:.1f}" text-anchor="end">{_tick_label(t)}</text>')
    ax = X(0) if x0 <= 0 <= x1 else left
    ay = Y(0) if y0 <= 0 <= y1 else h - bottom
    parts.append(f'<line x1="{left}" y1="{ay:.1f}" x2="{w - right}" y2="{ay:.1f}" style="stroke:var(--ink);stroke-width:1.3"/>')
    parts.append(f'<line x1="{ax:.1f}" y1="{top}" x2="{ax:.1f}" y2="{h - bottom}" style="stroke:var(--ink);stroke-width:1.3"/>')
    colors = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--thm)"]
    dashes = {"solid": "", "dashed": "stroke-dasharray:7 5;", "dotted": "stroke-dasharray:2 4;"}
    for i, s in enumerate(series):
        pts = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(s["xs"], s["ys"]))
        parts.append(f'<polyline points="{pts}" style="fill:none;stroke:{colors[i % 4]};stroke-width:2.4;{dashes[s["style"]]}"/>')
        if vector:
            (ax0, ax1), (ay0, ay1) = (X(v) for v in s["xs"]), (Y(v) for v in s["ys"])
            dx, dy = ax1 - ax0, ay1 - ay0
            n = math.hypot(dx, dy)
            if n > 1:
                ux, uy = dx / n, dy / n
                bx, by = ax1 - ux * 10, ay1 - uy * 10
                parts.append(f'<polygon points="{ax1:.1f},{ay1:.1f} {bx - uy * 4.5:.1f},{by + ux * 4.5:.1f} '
                             f'{bx + uy * 4.5:.1f},{by - ux * 4.5:.1f}" style="fill:{colors[i % 4]}"/>')
                if s["label"]:
                    lx, ly = ax1 + ux * 8, ay1 + uy * 8 + 4
                    anchor = "start" if ux >= -0.2 else "end"
                    parts.append(f'<text class="lbl" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
                                 f'style="fill:{colors[i % 4]}">{svg_text(s["label"])}</text>')
    for m in figure["marks"]:
        parts.append(f'<circle cx="{X(m["x"]):.1f}" cy="{Y(m["y"]):.1f}" r="4" style="fill:var(--ink)"/>')
        anchor = "end" if X(m["x"]) > w * 0.7 else "start"
        dx = -7 if anchor == "end" else 7
        parts.append(f'<text class="lbl" x="{X(m["x"]) + dx:.1f}" y="{Y(m["y"]) - 7:.1f}" text-anchor="{anchor}" '
                     f'style="fill:var(--ink)">{svg_text(m["label"])}</text>')
    parts.append(f'<text class="lbl" x="{w - right}" y="{h - 4}" text-anchor="end">{svg_text(figure["x_label"])}</text>')
    parts.append(f'<text class="lbl" x="{left - 40}" y="{top - 2}" text-anchor="start">{svg_text(figure["y_label"])}</text>')
    parts.append("</svg>")
    legend = "".join(
        f'<div><span class="legend-dot" style="background:{colors[i % 4]}"></span>{svg_label_html(s["label"])}</div>'
        for i, s in enumerate(series) if s["label"] and not vector
    )
    return f'<div style="overflow-x:auto">{"".join(parts)}</div>' + (f'<div class="fig-caption">{legend}</div>' if legend else "")


def svg_label_html(label: str) -> str:
    """Series legends are HTML; keep their math for MathJax."""
    return html.escape(label if "$" in label or not re.search(r"[_^\\]", label) else f"${label}$")
