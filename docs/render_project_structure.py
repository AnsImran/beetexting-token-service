"""Render the project_structure Mermaid diagram from README.md into a PNG.

Uses the mermaid.ink public API — no local Node.js or mermaid-cli required.
Mermaid does automatic graph layout, so arrows never overlap text and the
diagram is trivial to tweak: just edit the ```mermaid block in README.md
and re-run this script.

Usage (from repo root):
    python docs/render_project_structure.py

Output: docs/project_structure.png
"""

import base64
import re
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
OUTPUT_PATH = REPO_ROOT / "docs" / "project_structure.png"


def extract_project_structure_block(markdown_text: str) -> str | None:
    """Find the first ```mermaid block that looks like our project structure.

    We identify it by the presence of ``src/`` and ``Entrypoint`` which are
    both unique to the project structure diagram.
    """
    pattern = r"```mermaid\s*\n(.*?)```"
    for block in re.findall(pattern, markdown_text, re.DOTALL):
        if "src/" in block and "Entrypoint" in block:
            return block
    return None


def render_mermaid_to_png(mermaid_code: str, output_path: Path) -> None:
    """Render a Mermaid diagram to a PNG file via mermaid.ink."""
    encoded = base64.urlsafe_b64encode(mermaid_code.encode("utf-8")).decode("ascii")
    url = f"https://mermaid.ink/img/{encoded}?type=png&bgColor=white"
    print(f"  Downloading {output_path.name} from mermaid.ink ...")
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (render_project_structure.py)"}
    )
    with urllib.request.urlopen(req, timeout=60) as response:  # noqa: S310
        content = response.read()
    output_path.write_bytes(content)
    print(f"  Saved {output_path}  ({len(content):,} bytes)")


def main() -> int:
    readme = README_PATH.read_text(encoding="utf-8")
    block = extract_project_structure_block(readme)
    if block is None:
        print("ERROR: no project_structure Mermaid block found in README.md.")
        return 1
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    render_mermaid_to_png(block, OUTPUT_PATH)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
