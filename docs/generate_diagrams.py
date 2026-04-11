"""
Generate architecture and flow diagrams for the BEEtexting Token Service.

Run with:
    python docs/generate_diagrams.py

Outputs PNG files into the docs/ directory.
Requires: matplotlib (pip install matplotlib)
"""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for PNG generation

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

DOCS_DIR = Path(__file__).parent
DPI = 180


# ── Colour palette ──────────────────────────────────────────────────────────

COLOURS = {
    "bg":           "#FFFFFF",
    "primary":      "#1E3A5F",   # dark navy — titles, borders
    "secondary":    "#3B7DD8",   # medium blue — service boxes
    "accent":       "#F59E0B",   # amber — token / highlight
    "success":      "#10B981",   # green — healthy / OK
    "danger":       "#EF4444",   # red — errors
    "light_bg":     "#F0F4F8",   # light grey-blue — background boxes
    "card_bg":      "#FFFFFF",   # white — cards
    "text":         "#1E293B",   # near-black — body text
    "text_light":   "#64748B",   # grey — secondary text
    "beetexting":   "#FFD700",   # gold — BEEtexting brand
    "border":       "#CBD5E1",   # light border
}


def _add_rounded_box(ax, x, y, w, h, label, sublabel=None, colour="#3B7DD8",
                     text_colour="white", fontsize=11, sublabel_size=8):
    """Draw a rounded rectangle with centred text."""
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02",
        facecolor=colour,
        edgecolor=COLOURS["primary"],
        linewidth=1.5,
        zorder=2,
    )
    ax.add_patch(box)
    if sublabel:
        ax.text(x + w / 2, y + h / 2 + 0.015, label,
                ha="center", va="center", fontsize=fontsize,
                fontweight="bold", color=text_colour, zorder=3)
        ax.text(x + w / 2, y + h / 2 - 0.025, sublabel,
                ha="center", va="center", fontsize=sublabel_size,
                color=text_colour, alpha=0.85, zorder=3)
    else:
        ax.text(x + w / 2, y + h / 2, label,
                ha="center", va="center", fontsize=fontsize,
                fontweight="bold", color=text_colour, zorder=3)


def _add_arrow(ax, x1, y1, x2, y2, label=None, colour="#1E3A5F", style="->",
               connectionstyle="arc3,rad=0.0", lw=1.8, fontsize=8):
    """Draw an arrow between two points with optional label."""
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style,
        connectionstyle=connectionstyle,
        color=colour,
        linewidth=lw,
        mutation_scale=15,
        zorder=4,
    )
    ax.add_patch(arrow)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx, my + 0.02, label, ha="center", va="bottom",
                fontsize=fontsize, color=colour, fontstyle="italic", zorder=5)


# ═══════════════════════════════════════════════════════════════════════════
# DIAGRAM 1 — High-level Architecture
# ═══════════════════════════════════════════════════════════════════════════

def generate_architecture_diagram():
    """Create the high-level architecture overview."""
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(COLOURS["bg"])

    # ── Title ───────────────────────────────────────────────────────────
    ax.text(0.5, 0.96, "BEEtexting Token Service — Architecture",
            ha="center", va="top", fontsize=16, fontweight="bold",
            color=COLOURS["primary"])
    ax.text(0.5, 0.925, "Internal microservice for OAuth2 token management",
            ha="center", va="top", fontsize=10, color=COLOURS["text_light"])

    # ── Background zones ────────────────────────────────────────────────
    # Internal network zone
    internal_zone = FancyBboxPatch(
        (0.03, 0.08), 0.62, 0.8,
        boxstyle="round,pad=0.02",
        facecolor="#F0F7FF", edgecolor=COLOURS["border"],
        linewidth=1.5, linestyle="--", zorder=0,
    )
    ax.add_patch(internal_zone)
    ax.text(0.34, 0.87, "Internal Network (localhost only)",
            ha="center", fontsize=9, color=COLOURS["text_light"],
            fontstyle="italic")

    # External zone
    external_zone = FancyBboxPatch(
        (0.68, 0.08), 0.29, 0.8,
        boxstyle="round,pad=0.02",
        facecolor="#FFF7ED", edgecolor=COLOURS["border"],
        linewidth=1.5, linestyle="--", zorder=0,
    )
    ax.add_patch(external_zone)
    ax.text(0.825, 0.87, "External (Internet)",
            ha="center", fontsize=9, color=COLOURS["text_light"],
            fontstyle="italic")

    # ── Token Service (centre) ──────────────────────────────────────────
    _add_rounded_box(ax, 0.17, 0.52, 0.32, 0.12,
                     "BEEtexting Token Service",
                     "FastAPI  |  :8100  |  /api/v1/token",
                     colour=COLOURS["secondary"])

    # Token Manager inside
    _add_rounded_box(ax, 0.20, 0.38, 0.26, 0.08,
                     "TokenManager",
                     "Background refresh loop  |  CachedToken",
                     colour="#2563EB", fontsize=9, sublabel_size=7)

    # ── Sibling services (left) ─────────────────────────────────────────
    services = [
        ("SMS Sender Service", ":8200"),
        ("Worklist Service", ":8300"),
        ("Future Service N", ":8xxx"),
    ]
    y_positions = [0.76, 0.60, 0.44]
    for (name, port), y_pos in zip(services, y_positions):
        _add_rounded_box(ax, 0.04, y_pos, 0.11, 0.07, name, port,
                         colour="#6366F1", fontsize=8, sublabel_size=7)
        # Arrow: service → token service
        _add_arrow(ax, 0.15, y_pos + 0.035, 0.17, 0.58,
                   label="GET /token" if y_pos == 0.76 else None,
                   colour=COLOURS["success"],
                   connectionstyle="arc3,rad=0.15")

    # ── BEEtexting Cloud (right) ────────────────────────────────────────
    _add_rounded_box(ax, 0.71, 0.58, 0.23, 0.12,
                     "BEEtexting OAuth2",
                     "auth.beetexting.com/oauth2/token",
                     colour=COLOURS["accent"], text_colour=COLOURS["primary"],
                     fontsize=10, sublabel_size=7)

    _add_rounded_box(ax, 0.71, 0.36, 0.23, 0.12,
                     "BEEtexting SMS API",
                     "connect.beetexting.com/prod/...",
                     colour="#F97316", text_colour="white",
                     fontsize=10, sublabel_size=7)

    # Arrow: Token Manager → BEEtexting OAuth2
    _add_arrow(ax, 0.49, 0.47, 0.71, 0.62,
               label="POST client_credentials",
               colour=COLOURS["accent"], lw=2.2)

    # Arrow: Sibling → BEEtexting SMS (dashed to show they use the token)
    _add_arrow(ax, 0.15, 0.455, 0.71, 0.42,
               label="Bearer token + x-api-key",
               colour="#F97316", style="-|>",
               connectionstyle="arc3,rad=-0.15")

    # ── Legend ──────────────────────────────────────────────────────────
    legend_y = 0.16
    ax.text(0.05, legend_y + 0.06, "Flow:", fontsize=9,
            fontweight="bold", color=COLOURS["text"])

    legend_items = [
        (COLOURS["success"], "1. Services call Token Service for a cached token"),
        (COLOURS["accent"], "2. Token Service refreshes from BEEtexting (background)"),
        ("#F97316", "3. Services use token to call BEEtexting SMS API directly"),
    ]
    for i, (colour, text) in enumerate(legend_items):
        ax.plot([0.05], [legend_y + 0.03 - i * 0.035], "s",
                color=colour, markersize=8)
        ax.text(0.07, legend_y + 0.03 - i * 0.035, text,
                va="center", fontsize=8, color=COLOURS["text"])

    # ── Save ────────────────────────────────────────────────────────────
    output = DOCS_DIR / "architecture.png"
    fig.savefig(output, dpi=DPI, bbox_inches="tight",
                facecolor=COLOURS["bg"], pad_inches=0.3)
    plt.close(fig)
    print(f"  Created {output}")


# ═══════════════════════════════════════════════════════════════════════════
# DIAGRAM 2 — Token Lifecycle
# ═══════════════════════════════════════════════════════════════════════════

def generate_token_lifecycle_diagram():
    """Create the token fetch → cache → refresh lifecycle diagram."""
    fig, ax = plt.subplots(1, 1, figsize=(14, 9))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(COLOURS["bg"])

    # ── Title ───────────────────────────────────────────────────────────
    ax.text(0.5, 0.97, "Token Lifecycle — Fetch, Cache & Refresh",
            ha="center", va="top", fontsize=16, fontweight="bold",
            color=COLOURS["primary"])

    # ── Phase boxes ─────────────────────────────────────────────────────
    phases = [
        # (x, y, label, sublabel, colour)
        (0.04, 0.78, "1. STARTUP", "Service boots, calls start()", "#7C3AED"),
        (0.04, 0.60, "2. INITIAL FETCH", "POST to BEEtexting OAuth2", COLOURS["secondary"]),
        (0.04, 0.42, "3. VALIDATE & CACHE", "BeeTextingTokenResponse → CachedToken", COLOURS["success"]),
        (0.04, 0.24, "4. SERVE CALLERS", "GET /api/v1/token → return cached", "#6366F1"),
        (0.04, 0.06, "5. BACKGROUND REFRESH", "Sleep until buffer, then repeat step 2", COLOURS["accent"]),
    ]

    for x, y, label, sublabel, colour in phases:
        _add_rounded_box(ax, x, y, 0.26, 0.1, label, sublabel,
                         colour=colour, fontsize=10, sublabel_size=7)

    # Arrows between phases (downward flow)
    arrow_x = 0.17
    for i in range(len(phases) - 1):
        y_from = phases[i][1]
        y_to = phases[i + 1][1] + 0.1
        _add_arrow(ax, arrow_x, y_from, arrow_x, y_to,
                   colour=COLOURS["primary"], lw=1.5)

    # Loop-back arrow from phase 5 back to phase 2
    ax.annotate(
        "", xy=(0.04, 0.65), xytext=(0.04, 0.11),
        arrowprops=dict(
            arrowstyle="->", color=COLOURS["danger"],
            lw=2, connectionstyle="arc3,rad=-0.5",
        ), zorder=4,
    )
    ax.text(0.005, 0.40, "repeat\nevery\n~55 min", fontsize=7,
            ha="center", color=COLOURS["danger"], fontstyle="italic",
            rotation=0)

    # ── Detail panel (right side) ───────────────────────────────────────
    detail_bg = FancyBboxPatch(
        (0.35, 0.04), 0.62, 0.88,
        boxstyle="round,pad=0.02",
        facecolor="#F8FAFC", edgecolor=COLOURS["border"],
        linewidth=1, zorder=0,
    )
    ax.add_patch(detail_bg)
    ax.text(0.66, 0.90, "Implementation Details",
            ha="center", fontsize=13, fontweight="bold",
            color=COLOURS["primary"])

    details = [
        ("Pydantic Models (frozen, validated)", [
            "BeeTextingTokenResponse — validates upstream JSON",
            "  access_token: str (min_length=1, repr=False)",
            "  token_type: str (default 'Bearer')",
            "  expires_in: int (gt=0)",
            "",
            "CachedToken — in-memory state (frozen=True)",
            "  access_token: str (min_length=1, repr=False)",
            "  token_type: str (default 'Bearer')",
            "  expires_at_utc: datetime (UTC-aware)",
            "  fetched_at_utc: datetime (UTC-aware)",
            "  .is_expired → bool property",
        ]),
        ("Background Refresh Loop", [
            "1. Calculate seconds until refresh",
            "   = expires_at - buffer - now",
            "   (min 10s to prevent busy-loop)",
            "2. asyncio.sleep(seconds)",
            "3. POST client_credentials to BEEtexting",
            "4. Validate with BeeTextingTokenResponse",
            "5. Build new CachedToken",
            "6. Atomic swap under asyncio.Lock",
            "7. Repeat from step 1",
        ]),
        ("Retry & Error Handling", [
            f"Retries: configurable (default 3)",
            f"Backoff: exponential (default 2s base)",
            "Errors wrapped as TokenFetchError (502)",
            "No token → TokenNotAvailableError (503)",
            "Catch-all handler → generic 500",
        ]),
    ]

    y_cursor = 0.85
    for section_title, lines in details:
        ax.text(0.38, y_cursor, section_title, fontsize=10,
                fontweight="bold", color=COLOURS["secondary"])
        y_cursor -= 0.03
        for line in lines:
            if line == "":
                y_cursor -= 0.01
                continue
            ax.text(0.39, y_cursor, line, fontsize=7.5,
                    fontfamily="monospace", color=COLOURS["text"])
            y_cursor -= 0.025
        y_cursor -= 0.02

    # ── Save ────────────────────────────────────────────────────────────
    output = DOCS_DIR / "token_lifecycle.png"
    fig.savefig(output, dpi=DPI, bbox_inches="tight",
                facecolor=COLOURS["bg"], pad_inches=0.3)
    plt.close(fig)
    print(f"  Created {output}")


# ═══════════════════════════════════════════════════════════════════════════
# DIAGRAM 3 — Project Structure
# ═══════════════════════════════════════════════════════════════════════════

def generate_project_structure_diagram():
    """Create a visual map of the project files and their responsibilities."""
    fig, ax = plt.subplots(1, 1, figsize=(14, 7))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(COLOURS["bg"])

    ax.text(0.5, 0.96, "Project Structure & Module Responsibilities",
            ha="center", va="top", fontsize=16, fontweight="bold",
            color=COLOURS["primary"])

    # Define modules and their descriptions
    modules = [
        # (file, description, colour, column, row)
        ("main.py", "Entrypoint\nuvicorn startup", "#7C3AED", 0, 0),
        ("app.py", "FastAPI factory\nLifespan mgmt", COLOURS["secondary"], 1, 0),
        ("config.py", "Pydantic Settings\nAll env vars", "#059669", 2, 0),
        ("token_manager.py", "Core logic\nFetch/cache/refresh", COLOURS["accent"], 0, 1),
        ("schemas.py", "Pydantic v2 models\nValidation", "#EC4899", 1, 1),
        ("exceptions.py", "Custom errors\nFastAPI handlers", COLOURS["danger"], 2, 1),
        ("api/v1/router.py", "API endpoints\n/token /health /ping", "#6366F1", 0, 2),
        ("logging_config.py", "UTC logging\nStructured format", "#8B5CF6", 1, 2),
        ("tests/", "37 unit tests\n85%+ coverage", COLOURS["success"], 2, 2),
    ]

    x_start, y_start = 0.05, 0.78
    x_step, y_step = 0.33, 0.25
    box_w, box_h = 0.28, 0.15

    for filename, desc, colour, col, row in modules:
        x = x_start + col * x_step
        y = y_start - row * y_step
        _add_rounded_box(ax, x, y, box_w, box_h, filename, desc,
                         colour=colour, fontsize=10, sublabel_size=8)

    # Arrows showing dependencies: main → app → config, app → router, app → token_manager
    # main → app
    _add_arrow(ax, 0.33, 0.855, 0.38, 0.855, colour=COLOURS["primary"])
    # app → config
    _add_arrow(ax, 0.66, 0.855, 0.71, 0.855, colour=COLOURS["primary"])
    # app → token_manager
    _add_arrow(ax, 0.38, 0.78, 0.19, 0.68, colour=COLOURS["primary"],
               connectionstyle="arc3,rad=0.2")
    # app → router
    _add_arrow(ax, 0.38, 0.78, 0.19, 0.38, colour=COLOURS["primary"],
               connectionstyle="arc3,rad=0.3")
    # token_manager → schemas
    _add_arrow(ax, 0.33, 0.605, 0.38, 0.605, colour=COLOURS["primary"])
    # token_manager → exceptions
    _add_arrow(ax, 0.33, 0.57, 0.71, 0.605, colour=COLOURS["primary"],
               connectionstyle="arc3,rad=-0.1")
    # router → token_manager
    _add_arrow(ax, 0.19, 0.43, 0.19, 0.53, colour=COLOURS["primary"])
    # router → schemas
    _add_arrow(ax, 0.33, 0.355, 0.38, 0.605, colour=COLOURS["primary"],
               connectionstyle="arc3,rad=-0.3")

    output = DOCS_DIR / "project_structure.png"
    fig.savefig(output, dpi=DPI, bbox_inches="tight",
                facecolor=COLOURS["bg"], pad_inches=0.3)
    plt.close(fig)
    print(f"  Created {output}")


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Generating diagrams...")
    generate_architecture_diagram()
    generate_token_lifecycle_diagram()
    generate_project_structure_diagram()
    print("Done!")
