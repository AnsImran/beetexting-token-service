"""Render all Mermaid diagrams from README.md into PNG files.

GitHub renders ```mermaid blocks natively in the README, so no images are
referenced from the README itself.  This script exists purely to produce
offline PNG copies (for viewing the diagrams without GitHub, or embedding
them elsewhere).

Uses the mermaid.ink public API — stdlib only, no extra dependencies.
Mermaid handles layout automatically, so arrows never overlap text and the
diagrams are trivial to tweak: just edit the ```mermaid blocks in README.md
and re-run this script.

Usage (from repo root):
    python docs/render_diagrams.py

Output:
    docs/architecture.png
    docs/token_lifecycle.png
    docs/project_structure.png

The order of Mermaid blocks in README.md must match ``DIAGRAM_NAMES``.
"""

import base64
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
OUTPUT_DIR = REPO_ROOT / "docs"

# Friendly names for each Mermaid block, in the order they appear in README.md
DIAGRAM_NAMES: list[str] = [
    "architecture",
    "token_lifecycle",
    "project_structure",
]


def extract_mermaid_blocks(markdown_text: str) -> list[str]:
    """Return all ``` ```mermaid ``` ``` code blocks from a markdown document."""
    pattern = r"```mermaid\s*\n(.*?)```"
    return re.findall(pattern, markdown_text, re.DOTALL)


MAX_ATTEMPTS = 4
RETRY_DELAY_SECONDS = 3.0


def render_mermaid_to_png(mermaid_code: str, output_path: Path) -> None:
    """Render a single Mermaid diagram to PNG via the mermaid.ink service.

    Retries on transient 5xx errors with a short backoff, because
    mermaid.ink is a free public service and occasionally returns 503.

    Args:
        mermaid_code: The raw Mermaid source (without the ```mermaid fence).
        output_path: Where to write the PNG file.
    """
    encoded = base64.urlsafe_b64encode(mermaid_code.encode("utf-8")).decode("ascii")
    url = f"https://mermaid.ink/img/{encoded}?type=png&bgColor=white"
    # mermaid.ink rejects the default Python user-agent, so we set a browser one
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (render_diagrams.py)"}
    )

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(f"  Rendering {output_path.name} (attempt {attempt}/{MAX_ATTEMPTS}) ...")
            with urllib.request.urlopen(req, timeout=60) as response:  # noqa: S310
                content = response.read()
            output_path.write_bytes(content)
            print(f"  Saved {output_path.name}  ({len(content):,} bytes)")
            return
        except urllib.error.HTTPError as exc:
            if exc.code >= 500 and attempt < MAX_ATTEMPTS:
                print(f"    mermaid.ink returned {exc.code}, retrying in {RETRY_DELAY_SECONDS}s ...")
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            raise


def main() -> int:
    """Extract all Mermaid blocks from README.md and render each to PNG."""
    readme_text = README_PATH.read_text(encoding="utf-8")
    blocks = extract_mermaid_blocks(readme_text)

    if not blocks:
        print("ERROR: No ```mermaid blocks found in README.md.", file=sys.stderr)
        return 1

    if len(blocks) != len(DIAGRAM_NAMES):
        print(
            f"ERROR: Found {len(blocks)} Mermaid block(s) but expected "
            f"{len(DIAGRAM_NAMES)} (one per entry in DIAGRAM_NAMES).",
            file=sys.stderr,
        )
        print(f"Expected names (in order): {DIAGRAM_NAMES}", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Found {len(blocks)} Mermaid block(s) in README.md.")

    for name, block in zip(DIAGRAM_NAMES, blocks, strict=True):
        output_path = OUTPUT_DIR / f"{name}.png"
        try:
            render_mermaid_to_png(block, output_path)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED to render {name}: {exc}", file=sys.stderr)
            return 1

    print()
    print(f"Done. PNGs saved to {OUTPUT_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
