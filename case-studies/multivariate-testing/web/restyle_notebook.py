"""Restyles the nbconvert HTML export of Direct_Mail_Multivariate_Testing.ipynb into
the portfolio's research-notebook layout.

The notebook's own cells are kept as they are (code, outputs, markdown); the script
only changes how they are presented:

  - a section sidebar built from the notebook's h2 headings
  - a summary header (title, subtitle, four headline figures, the data disclosure)
  - code cells as cards with a copy button, and outputs beneath them
  - markdown cells holding a "Recommendation" bullet split into an Interpretation
    callout and a Decision callout
  - a right-hand rail with the key decisions, section progress, and related documents
  - a "Hide code" toggle

Run from case-studies/multivariate-testing after re-exporting the notebook:

    jupyter nbconvert --to html Direct_Mail_Multivariate_Testing.ipynb \
        --output direct_mail_multivariate_testing
    python3 web/restyle_notebook.py direct_mail_multivariate_testing.html \
        web/direct_mail_multivariate_testing.html

The input must be a fresh nbconvert export; output this script produced is refused.
Styles live in web/notebook.css and are inlined into the page. The headline figures
and key decisions below are quoted from the notebook's outputs; update them if a
re-run changes the results.
"""

import html
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent

KERNEL = "Python (base) · 3.12"  # the notebook's kernelspec display name and language version

# Sidebar labels, keyed by the start of each h2 heading's text.
SECTION_LABELS = [
    ("Abstract", "Abstract"),
    ("1.0", "Introduction"),
    ("2.0", "Stage 1 · Mailer A/B Test"),
    ("3.0", "Stage 2 · Creative × Timing"),
    ("4.0", "Stage 3 · Landing-Page Test"),
    ("5.0", "Summary & Conclusions"),
]

# (icon, value, label) quoted from the notebook's outputs.
STATS = [
    ("mail", "3", "designs fielded"),
    ("dollar", "$195K", "mailer savings, Creative A"),
    ("bars", "34% vs 60%", "completion, weakest vs strongest page"),
    ("flask", "24 runs", "instead of 96"),
]

# (title, detail, section index) — section index into SECTION_LABELS.
DECISIONS = [
    ("Adopt the lower-cost mailer", "Stage 1 · p = 0.45", 2),
    ("Mail mid-month", "Stage 2 · p < 0.001", 3),
    ("Use a professional design with trust badges", "Stage 3 · 60% completion", 4),
    ("Choose hero imagery on brand grounds", "Stage 3 · effect too small to act on", 4),
]

RELATED = [
    ("Case study", "case-study.html"),
    ("Executive presentation", "executive-presentation.html"),
    ("Analytical plan", "analytical-plan.html"),
]

ICONS = {
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    "dollar": '<path d="M12 2v20M17 6.5c-.8-1.5-2.7-2.5-5-2.5-2.8 0-5 1.6-5 3.8 0 5.2 10 2.7 10 8.2 0 2.3-2.2 4-5 4-2.4 0-4.4-1.1-5.2-2.8"/>',
    "bars": '<path d="M5 20v-6M10 20V9M15 20v-9M20 20V5"/>',
    "flask": '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-9V3M7.3 14h9.4"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "link": '<path d="M10 14a5 5 0 0 0 7.1 0l3-3a5 5 0 0 0-7.1-7.1l-1.2 1.2M14 10a5 5 0 0 0-7.1 0l-3 3a5 5 0 0 0 7.1 7.1l1.2-1.2"/>',
    "shield": '<path d="M12 2l8 3v6c0 5-3.4 9.3-8 11-4.6-1.7-8-6-8-11V5z"/>',
}


def icon(name, cls="icon"):
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


def section_label(heading_text):
    for prefix, label in SECTION_LABELS:
        if heading_text.startswith(prefix):
            return label
    raise SystemExit(f"no sidebar label for section heading {heading_text!r}; update SECTION_LABELS")


def strip_number(heading_text):
    """'2.0 Part 1: A/B Test — Mailer Creative' -> 'Part 1: A/B Test — Mailer Creative'."""
    return re.sub(r"^\d+\.\d+\s+", "", heading_text)


def heading_text(tag):
    return tag.get_text().replace("¶", "").strip()


def inner(tag):
    return "".join(str(child) for child in tag.children)


def recommendation_callouts(rendered):
    """Split a markdown cell whose list holds a 'Recommendation' bullet into callouts.
    Returns None when the cell has no such bullet."""
    for ul in rendered.find_all("ul"):
        items = ul.find_all("li", recursive=False)
        rec = next(
            (li for li in items if li.find("strong") and li.find("strong").get_text(strip=True).startswith("Recommendation")),
            None,
        )
        if rec is None:
            continue
        rec.find("strong").decompose()
        decision = inner(rec).strip().lstrip(":").strip()
        decision = decision[:1].upper() + decision[1:]
        others = "".join(str(li) for li in items if li is not rec)
        ul.decompose()
        lead = inner(rendered).strip()
        interp = (
            f'<div class="callout interp"><span class="callout-mark" aria-hidden="true">!</span>'
            f'<div><p class="callout-title">Interpretation</p><ul>{others}</ul></div></div>'
            if others else ""
        )
        decided = (
            f'<div class="callout decision"><span class="callout-mark ok">{icon("check")}</span>'
            f'<div><p class="callout-title">Decision</p><p>{decision}</p></div></div>'
        )
        return (f'<div class="md">{lead}</div>' if lead else "") + f'<div class="callouts">{interp}{decided}</div>'
    return None


def code_cell(cell):
    prompt = cell.select_one(".jp-InputPrompt").get_text(strip=True)
    pre = cell.select_one(".highlight pre")
    parts = [
        '<div class="nb-cell code-cell">'
        f'<div class="prompt in">{html.escape(prompt)}</div>'
        '<div class="code-card"><button type="button" class="copy" aria-label="Copy code">Copy</button>'
        f"{pre}</div></div>"
    ]
    for child in cell.select(".jp-OutputArea-child"):
        out_prompt = child.select_one(".jp-OutputPrompt")
        label = out_prompt.get_text(strip=True) if out_prompt else ""
        output = child.select_one(".jp-OutputArea-output")
        if output is None:
            continue
        classes = output.get("class", [])
        if "jp-RenderedImage" in classes:
            body = f'<div class="out-image">{inner(output)}</div>'
        elif output.get("data-mime-type") == "text/plain" or "jp-RenderedText" in classes:
            body = f'<div class="out-text">{inner(output)}</div>'
        else:
            body = f'<div class="out-html">{inner(output)}</div>'
        parts.append(
            '<div class="nb-cell out-cell">'
            f'<div class="prompt out">{html.escape(label)}</div>{body}</div>'
        )
    return "".join(parts)


def build(src_html):
    soup = BeautifulSoup(src_html, "html.parser")
    if soup.find(attrs={"data-restyled": "notebook"}):
        raise SystemExit("input is already restyled; pass a fresh nbconvert export")
    cells = soup.select("div.jp-Cell")
    assert len(cells) > 2, "expected an nbconvert export with notebook cells"

    title_cell = cells[0].select_one(".jp-RenderedMarkdown")
    title = title_cell.find("h1").get_text(strip=True)
    subtitle = title_cell.find("p").get_text(strip=True)
    disclosure_cell = cells[1].select_one(".jp-RenderedMarkdown")
    disclosure = "".join(str(li) for li in disclosure_cell.find_all("li"))
    assert disclosure, "expected the data disclosure bullets in the second cell"

    body, sections = [], []
    for cell in cells[2:]:
        if "jp-CodeCell" in cell.get("class", []):
            body.append(code_cell(cell))
            continue
        rendered = cell.select_one(".jp-RenderedMarkdown")
        h2 = rendered.find("h2")
        if h2 is not None:
            text = heading_text(h2)
            number = len(sections) + 1
            anchor = h2.get("id")
            sections.append((anchor, section_label(text)))
            h2.decompose()
            if number > 1:
                body.append("</section>")
            body.append(
                f'<section class="nb-section" id="{html.escape(anchor, quote=True)}" data-section="{number}">'
                f'<h2 class="section-head"><span class="section-num">{number:02d}</span>{html.escape(strip_number(text))}</h2>'
            )
            rest = inner(rendered).strip()
            if rest:
                body.append(f'<div class="md">{rest}</div>')
            continue
        callouts = recommendation_callouts(rendered)
        body.append(callouts if callouts is not None else f'<div class="md">{inner(rendered)}</div>')
    body.append("</section>")

    stats = "".join(
        f'<div class="stat">{icon(name)}<div><b>{html.escape(value)}</b><span>{html.escape(label)}</span></div></div>'
        for name, value, label in STATS
    )
    toc = "".join(
        f'<li><a href="#{html.escape(anchor, quote=True)}" data-toc="{i + 1}"><span>{i + 1:02d}</span>{html.escape(label)}</a></li>'
        for i, (anchor, label) in enumerate(sections)
    )
    decisions = "".join(
        f'<li><a href="#{html.escape(sections[idx][0], quote=True)}"><span class="decision-num">{i + 1}</span>'
        f'<span><b>{html.escape(t)}</b><small>{html.escape(d)}</small></span></a></li>'
        for i, (t, d, idx) in enumerate(DECISIONS)
    )
    progress = "".join(
        f'<li data-progress="{i + 1}"><span class="progress-mark">{icon("check")}</span>{html.escape(label)}</li>'
        for i, (_, label) in enumerate(sections)
    )
    related = "".join(
        f'<li><a href="{href}" target="_blank" rel="noopener">{icon("link")}{html.escape(name)}</a></li>'
        for name, href in RELATED
    )

    css = (HERE / "notebook.css").read_text()
    template = (HERE / "notebook_template.html").read_text()
    replacements = {
        "{{TITLE}}": html.escape(title),
        "{{SUBTITLE}}": html.escape(subtitle),
        "{{CSS}}": css,
        "{{KERNEL}}": html.escape(KERNEL),
        "{{STATS}}": stats,
        "{{DISCLOSURE}}": disclosure,
        "{{TOC}}": toc,
        "{{BODY}}": "\n".join(body),
        "{{DECISIONS}}": decisions,
        "{{PROGRESS}}": progress,
        "{{RELATED}}": related,
        "{{SHIELD}}": icon("shield"),
    }
    page = template
    for key, value in replacements.items():
        assert key in page, f"template is missing {key}"
        page = page.replace(key, value)
    return page


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.write_text(build(src.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
