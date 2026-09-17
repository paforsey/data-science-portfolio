"""Merges executed notebooks into one, so a study split across notebooks builds into a single page.

    python3 tools/notebook-restyle/merge_notebooks.py <out.ipynb> <first.ipynb> <second.ipynb> [...]

The merged notebook is a build artifact: export it with `jupyter nbconvert --to html` and pass
the export to restyle_notebook.py as usual. Never edit it.

  - cell 0 of every notebook is its title cell; its h1 is never treated as a section
  - the first notebook is kept whole: its title, notice, and overview cells lead the page
  - each later notebook drops the markdown ahead of its first h1 (title, disclosure, abstract),
    except a cell whose heading starts with "Initialize"; that cell and the code cells ahead of
    the first h1 move into the overview, right after the first notebook's own setup
  - setup code identical to a cell already in the overview is shown once; if all of a later
    notebook's setup is duplicated, its "Initialize" cell is dropped too
  - every later notebook's h1 sections follow the first notebook's, in argument order
  - execution counts are renumbered so the page reads as one run
  - a code cell with source but no execution count is refused: execute every notebook first
"""

import re
import sys

import nbformat

H1 = re.compile(r"<h1[\s>]|^# ", re.M)
HEADING = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>|^#{1,6} (.+)$", re.M)


def first_h1(cells):
    # Cell 0 is the title cell, whose h1 is the page title rather than a section.
    for i, cell in enumerate(cells[1:], start=1):
        if cell.cell_type == "markdown" and H1.search(cell.source):
            return i
    raise SystemExit("notebook has no h1 section heading after its title cell")


def is_setup_markdown(cell):
    match = HEADING.search(cell.source)
    return bool(match) and re.sub(r"<[^>]+>", "", match.group(1) or match.group(2)).strip().startswith("Initialize")


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    out, paths = sys.argv[1], sys.argv[2:]
    notebooks = [nbformat.read(p, as_version=4) for p in paths]

    for path, nb in zip(paths, notebooks):
        for cell in nb.cells:
            if cell.cell_type == "code" and cell.source.strip() and cell.execution_count is None:
                raise SystemExit(f"{path} has unexecuted code cells; run it before merging")

    first = notebooks[0]
    split = first_h1(first.cells)
    lead, bodies = list(first.cells[:split]), [first.cells[split:]]

    for nb in notebooks[1:]:
        split = first_h1(nb.cells)
        shown = {c.source.strip() for c in lead if c.cell_type == "code"}
        setup = [c for c in nb.cells[:split] if c.cell_type == "code" and c.source.strip() not in shown]
        if setup:
            lead += [c for c in nb.cells[:split] if is_setup_markdown(c)] + setup
        bodies.append(nb.cells[split:])

    merged = nbformat.v4.new_notebook(metadata=first.metadata)
    merged.cells = lead + [cell for body in bodies for cell in body]

    count = 0
    for cell in merged.cells:
        if cell.cell_type == "code" and cell.execution_count is not None:
            count += 1
            cell.execution_count = count
            for output in cell.get("outputs", []):
                if "execution_count" in output:
                    output["execution_count"] = count

    nbformat.write(merged, out)
    sections = sum(1 for c in merged.cells[1:] if c.cell_type == "markdown" and H1.search(c.source))
    print(f"wrote {out}: {len(merged.cells)} cells, {sections} h1 sections from {len(paths)} notebooks")


if __name__ == "__main__":
    main()
