"""
Generate architecture and flow diagrams for the BEEtexting Token Service.

Run with:
    python docs/generate_diagrams.py

Outputs PNG and SVG files into the docs/ directory.
Requires: matplotlib (pip install matplotlib)
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

DOCS_DIR = Path(__file__).parent
DPI = 200

# ── Colour palette ──────────────────────────────────────────────────────────

C = {
    "bg":         "#FFFFFF",
    "primary":    "#1E3A5F",
    "blue":       "#3B7DD8",
    "dark_blue":  "#2563EB",
    "indigo":     "#6366F1",
    "purple":     "#7C3AED",
    "pink":       "#EC4899",
    "amber":      "#F59E0B",
    "orange":     "#F97316",
    "green":      "#10B981",
    "dark_green": "#059669",
    "red":        "#EF4444",
    "text":       "#1E293B",
    "text_light": "#64748B",
    "border":     "#CBD5E1",
    "zone_int":   "#F0F7FF",
    "zone_ext":   "#FFF7ED",
    "detail_bg":  "#F8FAFC",
}


def _box(ax, x, y, w, h, label, sub=None, *, col="#3B7DD8", tcol="white",
         fs=11, sfs=8, lw=1.5, edge=None):
    """Draw a rounded box with centred label and optional sublabel."""
    edge = edge or C["primary"]
    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.015",
        facecolor=col, edgecolor=edge, linewidth=lw, zorder=2,
    )
    ax.add_patch(patch)
    cy = y + h / 2
    if sub:
        ax.text(x + w / 2, cy + h * 0.14, label, ha="center", va="center",
                fontsize=fs, fontweight="bold", color=tcol, zorder=3)
        ax.text(x + w / 2, cy - h * 0.18, sub, ha="center", va="center",
                fontsize=sfs, color=tcol, alpha=0.9, zorder=3)
    else:
        ax.text(x + w / 2, cy, label, ha="center", va="center",
                fontsize=fs, fontweight="bold", color=tcol, zorder=3)


def _arrow(ax, x1, y1, x2, y2, *, label=None, col="#1E3A5F", lw=1.8,
           rad=0.0, style="->", lx=None, ly=None, lfs=8, lha="center"):
    """Draw an arrow with optional label at midpoint or custom position."""
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle=style, linewidth=lw,
        connectionstyle=f"arc3,rad={rad}", color=col, mutation_scale=14, zorder=4,
    )
    ax.add_patch(arrow)
    if label:
        tx = lx if lx is not None else (x1 + x2) / 2
        ty = ly if ly is not None else (y1 + y2) / 2 + 0.018
        ax.text(tx, ty, label, ha=lha, va="bottom", fontsize=lfs,
                color=col, fontstyle="italic", zorder=5)


def _save(fig, name):
    """Save as both PNG and SVG."""
    for ext in ("png", "svg"):
        p = DOCS_DIR / f"{name}.{ext}"
        fig.savefig(p, dpi=DPI, bbox_inches="tight", facecolor=C["bg"], pad_inches=0.3)
        print(f"  {p}")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════
# DIAGRAM 1 — Architecture
# ═══════════════════════════════════════════════════════════════════════════

def gen_architecture():
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])

    # Title
    ax.text(0.50, 0.96, "BEEtexting Token Service — Architecture",
            ha="center", va="top", fontsize=17, fontweight="bold", color=C["primary"])
    ax.text(0.50, 0.93, "Internal microservice for OAuth2 token management",
            ha="center", va="top", fontsize=10, color=C["text_light"])

    # ── Zones ───────────────────────────────────────────────────────────
    ax.add_patch(FancyBboxPatch(
        (0.02, 0.06), 0.58, 0.83, boxstyle="round,pad=0.015",
        facecolor=C["zone_int"], edgecolor=C["border"], lw=1.5, ls="--", zorder=0))
    ax.text(0.31, 0.88, "Internal Network  (localhost only)",
            ha="center", fontsize=9, color=C["text_light"], fontstyle="italic")

    ax.add_patch(FancyBboxPatch(
        (0.63, 0.06), 0.35, 0.83, boxstyle="round,pad=0.015",
        facecolor=C["zone_ext"], edgecolor=C["border"], lw=1.5, ls="--", zorder=0))
    ax.text(0.805, 0.88, "External  (Internet)",
            ha="center", fontsize=9, color=C["text_light"], fontstyle="italic")

    # ── Sibling services (left column) ──────────────────────────────────
    svc_x, svc_w, svc_h = 0.04, 0.18, 0.09
    services = [
        ("SMS Sender", ":8200", 0.74),
        ("Worklist Service", ":8300", 0.60),
        ("Future Service N", ":8xxx", 0.46),
    ]
    for name, port, sy in services:
        _box(ax, svc_x, sy, svc_w, svc_h, name, port,
             col=C["indigo"], fs=9, sfs=7)

    # ── Token Service (centre) ──────────────────────────────────────────
    ts_x, ts_y, ts_w, ts_h = 0.26, 0.56, 0.30, 0.14
    _box(ax, ts_x, ts_y, ts_w, ts_h,
         "BEEtexting Token Service",
         "FastAPI  |  :8100  |  /api/v1/token",
         col=C["blue"], fs=12, sfs=8)

    # TokenManager sub-box
    tm_x, tm_y, tm_w, tm_h = 0.28, 0.40, 0.26, 0.10
    _box(ax, tm_x, tm_y, tm_w, tm_h,
         "TokenManager",
         "Background refresh  |  CachedToken",
         col=C["dark_blue"], fs=10, sfs=7)

    # ── BEEtexting cloud (right column) ─────────────────────────────────
    bt_x, bt_w, bt_h = 0.66, 0.29, 0.12
    _box(ax, bt_x, 0.60, bt_w, bt_h,
         "BEEtexting OAuth2",
         "auth.beetexting.com",
         col=C["amber"], tcol=C["primary"], fs=11, sfs=8)

    _box(ax, bt_x, 0.38, bt_w, bt_h,
         "BEEtexting SMS API",
         "connect.beetexting.com",
         col=C["orange"], fs=11, sfs=8)

    # ── Arrows ──────────────────────────────────────────────────────────
    # Services → Token Service
    for sy in (0.74, 0.60, 0.46):
        _arrow(ax, svc_x + svc_w, sy + svc_h / 2, ts_x, ts_y + ts_h / 2,
               col=C["green"], rad=0.15)
    # Label only on the top arrow
    ax.text(0.215, 0.81, "GET /api/v1/token", fontsize=8,
            color=C["green"], fontstyle="italic", ha="center")

    # TokenManager → BEEtexting OAuth2
    _arrow(ax, tm_x + tm_w, tm_y + tm_h / 2, bt_x, 0.66,
           label="POST client_credentials", col=C["amber"], lw=2.2,
           rad=-0.15, lx=0.60, ly=0.53)

    # Sibling → BEEtexting SMS API (uses token directly)
    _arrow(ax, svc_x + svc_w, 0.46 + svc_h / 2, bt_x, 0.44,
           label="Bearer token + x-api-key", col=C["orange"], lw=1.8,
           rad=-0.08, lx=0.44, ly=0.47)

    # ── Legend ──────────────────────────────────────────────────────────
    ly = 0.22
    ax.text(0.04, ly, "Flow:", fontsize=10, fontweight="bold", color=C["text"])
    items = [
        (C["green"],  "1. Sibling services call Token Service for a cached token"),
        (C["amber"],  "2. TokenManager refreshes from BEEtexting OAuth2 (background loop)"),
        (C["orange"], "3. Sibling services use the token to call BEEtexting SMS API directly"),
    ]
    for i, (colour, text) in enumerate(items):
        yy = ly - 0.045 * (i + 1)
        ax.plot(0.04, yy, "s", color=colour, markersize=9)
        ax.text(0.065, yy, text, va="center", fontsize=9, color=C["text"])

    _save(fig, "architecture")


# ═══════════════════════════════════════════════════════════════════════════
# DIAGRAM 2 — Token Lifecycle
# ═══════════════════════════════════════════════════════════════════════════

def gen_lifecycle():
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])

    # Title
    ax.text(0.50, 0.97, "Token Lifecycle — Fetch, Cache & Refresh",
            ha="center", va="top", fontsize=17, fontweight="bold", color=C["primary"])

    # ── Phase boxes (left column) ───────────────────────────────────────
    bx, bw, bh = 0.06, 0.28, 0.10
    gap = 0.04
    phases = [
        ("1. STARTUP",            "Service boots, calls start()",                C["purple"]),
        ("2. INITIAL FETCH",      "POST to BEEtexting OAuth2",                   C["blue"]),
        ("3. VALIDATE & CACHE",   "BeeTextingTokenResponse \u2192 CachedToken",  C["green"]),
        ("4. SERVE CALLERS",      "GET /api/v1/token \u2192 return cached",      C["indigo"]),
        ("5. BACKGROUND REFRESH", "Sleep until buffer, repeat from step 2",      C["amber"]),
    ]
    y_top = 0.84
    ys = []
    for i, (label, sub, col) in enumerate(phases):
        y = y_top - i * (bh + gap)
        ys.append(y)
        tcol = C["primary"] if col == C["amber"] else "white"
        _box(ax, bx, y, bw, bh, label, sub, col=col, fs=10, sfs=7, tcol=tcol)

    # Down-arrows between phases
    cx = bx + bw / 2
    for i in range(len(ys) - 1):
        _arrow(ax, cx, ys[i], cx, ys[i + 1] + bh, col=C["primary"], lw=1.5)

    # Loop-back arrow: step 5 → step 2
    loop_x = bx - 0.02
    ax.annotate(
        "", xy=(loop_x + 0.02, ys[1] + bh / 2),
        xytext=(loop_x + 0.02, ys[4] + bh / 2),
        arrowprops=dict(arrowstyle="-|>", color=C["red"], lw=2.2,
                        connectionstyle="arc3,rad=-0.6"),
        zorder=4)
    ax.text(loop_x - 0.025, (ys[1] + ys[4]) / 2 + bh / 2,
            "repeat\nevery\n~55 min", fontsize=8, ha="center",
            color=C["red"], fontweight="bold")

    # ── Detail panel (right side) ───────────────────────────────────────
    dx, dw = 0.40, 0.56
    ax.add_patch(FancyBboxPatch(
        (dx, 0.04), dw, 0.90, boxstyle="round,pad=0.02",
        facecolor=C["detail_bg"], edgecolor=C["border"], lw=1, zorder=0))

    ax.text(dx + dw / 2, 0.92, "Implementation Details",
            ha="center", fontsize=14, fontweight="bold", color=C["primary"])

    sections = [
        ("Pydantic Models  (frozen, validated)", [
            "",
            "BeeTextingTokenResponse",
            "    access_token : str   (min_length=1, repr=False)",
            "    token_type   : str   (default 'Bearer')",
            "    expires_in   : int   (gt=0)",
            "",
            "CachedToken  (frozen=True)",
            "    access_token   : str      (min_length=1, repr=False)",
            "    token_type     : str      (default 'Bearer')",
            "    expires_at_utc : datetime (UTC-aware)",
            "    fetched_at_utc : datetime (UTC-aware)",
            "    .is_expired    \u2192 bool    (property)",
        ]),
        ("Background Refresh Loop", [
            "",
            "1. Calculate seconds until refresh",
            "     = expires_at \u2212 buffer \u2212 now   (min 10 s)",
            "2. asyncio.sleep(seconds)",
            "3. POST client_credentials to BEEtexting",
            "4. Validate with BeeTextingTokenResponse",
            "5. Build new CachedToken",
            "6. Atomic swap under asyncio.Lock",
            "7. Go to step 1",
        ]),
        ("Retry & Error Handling", [
            "",
            "Retries : configurable   (default 3)",
            "Backoff : exponential    (default 2 s base)",
            "Errors  \u2192 TokenFetchError        (502)",
            "No token\u2192 TokenNotAvailableError (503)",
            "Catch-all handler        \u2192 generic 500",
        ]),
    ]

    ty = 0.885
    lm = dx + 0.03  # left margin for text
    for title, lines in sections:
        ax.text(lm, ty, title, fontsize=11, fontweight="bold", color=C["blue"])
        ty -= 0.005
        for line in lines:
            if line == "":
                ty -= 0.012
                continue
            ax.text(lm + 0.01, ty, line, fontsize=7.5,
                    fontfamily="monospace", color=C["text"])
            ty -= 0.025
        ty -= 0.015

    _save(fig, "token_lifecycle")


# ═══════════════════════════════════════════════════════════════════════════
# DIAGRAM 3 — Project Structure
# ═══════════════════════════════════════════════════════════════════════════

def gen_structure():
    fig, ax = plt.subplots(figsize=(18, 10))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])

    ax.text(0.50, 0.96, "Project Structure & Module Responsibilities",
            ha="center", va="top", fontsize=17, fontweight="bold", color=C["primary"])
    ax.text(0.50, 0.93, "Arrows show import dependencies",
            ha="center", va="top", fontsize=10, color=C["text_light"])

    # Grid layout: 3 columns x 3 rows, generous spacing
    cols = [0.05, 0.37, 0.69]
    rows = [0.73, 0.50, 0.27]
    bw, bh = 0.26, 0.13

    modules = [
        # (col, row, filename, description, colour)
        (0, 0, "main.py",             "Entrypoint\nuvicorn startup",              C["purple"]),
        (1, 0, "app.py",              "FastAPI factory\nLifespan management",     C["blue"]),
        (2, 0, "config.py",           "Pydantic Settings\nAll env vars validated", C["dark_green"]),
        (0, 1, "token_manager.py",    "Core logic\nFetch / cache / refresh",      C["amber"]),
        (1, 1, "schemas.py",          "Pydantic v2 models\nFrozen, validated",    C["pink"]),
        (2, 1, "exceptions.py",       "Custom errors\nFastAPI handlers",          C["red"]),
        (0, 2, "api/v1/router.py",    "API endpoints\n/token  /health  /ping",   C["indigo"]),
        (1, 2, "logging_config.py",   "UTC logging\nStructured format",          "#8B5CF6"),
        (2, 2, "tests/  (37 tests)",  "Config, TokenManager,\nAPI, Schema tests", C["green"]),
    ]

    # Draw all boxes
    positions = {}
    for ci, ri, fname, desc, colour in modules:
        x, y = cols[ci], rows[ri]
        tcol = C["primary"] if colour in (C["amber"],) else "white"
        _box(ax, x, y, bw, bh, fname, desc, col=colour, fs=11, sfs=8, tcol=tcol)
        positions[fname] = (x, y)

    # Helper to get box edge points
    def mid(name):
        x, y = positions[name]
        return x + bw / 2, y + bh / 2

    def right(name):
        x, y = positions[name]
        return x + bw, y + bh / 2

    def left(name):
        x, y = positions[name]
        return x, y + bh / 2

    def bottom(name):
        x, y = positions[name]
        return x + bw / 2, y

    def top(name):
        x, y = positions[name]
        return x + bw / 2, y + bh

    # Dependency arrows
    deps = [
        # (from, to, rad)
        ("main.py", "app.py", 0.0),
        ("app.py", "config.py", 0.0),
        ("app.py", "token_manager.py", 0.2),
        ("app.py", "api/v1/router.py", 0.3),
        ("token_manager.py", "schemas.py", 0.0),
        ("token_manager.py", "exceptions.py", -0.15),
        ("api/v1/router.py", "token_manager.py", 0.0),
        ("api/v1/router.py", "schemas.py", -0.2),
    ]

    for src, dst, rad in deps:
        # Pick edge points based on relative position
        sx, sy = positions[src]
        dx, dy = positions[dst]

        if sy == dy:  # same row → right edge to left edge
            x1, y1 = right(src)
            x2, y2 = left(dst)
        elif sx == dx:  # same column → bottom to top
            x1, y1 = bottom(src)
            x2, y2 = top(dst)
        elif dy < sy and dx > sx:  # down-right diagonal
            x1, y1 = right(src)
            x2, y2 = left(dst)
            x1, y1 = bottom(src)[0] + 0.05, bottom(src)[1]
            x2, y2 = top(dst)[0] - 0.05, top(dst)[1]
        elif dy < sy and dx == sx:  # straight down
            x1, y1 = bottom(src)
            x2, y2 = top(dst)
        elif dy > sy:  # going up
            x1, y1 = top(src)
            x2, y2 = bottom(dst)
        else:
            x1, y1 = right(src)
            x2, y2 = left(dst)

        _arrow(ax, x1, y1, x2, y2, col="#475569", lw=1.5, rad=rad)

    # Legend at bottom
    ax.text(0.05, 0.17, "Legend:", fontsize=10, fontweight="bold", color=C["text"])
    legend = [
        (C["purple"],     "Entrypoint"),
        (C["blue"],       "App factory"),
        (C["dark_green"], "Configuration"),
        (C["amber"],      "Core logic"),
        (C["pink"],       "Data models"),
        (C["red"],        "Error handling"),
        (C["indigo"],     "API layer"),
        ("#8B5CF6",       "Logging"),
        (C["green"],      "Tests"),
    ]
    for i, (colour, label) in enumerate(legend):
        col_idx = i % 3
        row_idx = i // 3
        lx = 0.05 + col_idx * 0.30
        ly = 0.13 - row_idx * 0.04
        ax.plot(lx, ly, "s", color=colour, markersize=10)
        ax.text(lx + 0.02, ly, label, va="center", fontsize=9, color=C["text"])

    _save(fig, "project_structure")


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Generating diagrams...")
    gen_architecture()
    gen_lifecycle()
    gen_structure()
    print("Done!")
