"""Extract HWP text through pyhwp XML, preserving paragraph/cell provenance.

This produces intermediate data, not final RAG chunks. No LLM/API is used.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

from lxml import etree


def nearest(node, tag):
    return next((a for a in node.iterancestors() if a.tag == tag), None)


def paragraph_text(paragraph):
    # Nested tables contain their own Paragraph elements; exclude their text
    # here to prevent duplicating it in the enclosing paragraph.
    parts = []
    for node in paragraph.iter():
        if nearest(node, "Paragraph") is not paragraph:
            continue
        if node.tag == "Text":
            parts.append(node.text or "")
        elif node.tag == "ControlChar":
            if node.get("name") == "TAB":
                parts.append("\t")
            elif node.get("name") in {"FIXWIDTH_SPACE", "NBSPACE"}:
                parts.append(" ")
            elif node.get("name") == "LINE_BREAK":
                parts.append("\n")
    return "".join(parts)


def cell_path(node):
    result = []
    for cell in reversed(list(node.iterancestors("TableCell"))):
        table = nearest(cell, "TableControl")
        result.append({
            "table_id": table.get("table-id"),
            **{key: int(cell.get(key)) for key in ("row", "col", "rowspan", "colspan")},
        })
    return result


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")


def extract(source, output):
    output.mkdir(parents=True, exist_ok=True)
    base = output / source.stem
    xml_path = base.with_suffix(".xml")
    subprocess.run([
        sys.executable, "-c", "from hwp5.hwp5proc import main; main()",
        "xml", "--output", str(xml_path), str(source)
    ], check=True)
    subprocess.run([
        sys.executable, "-c", "from hwp5.hwp5txt import main; main()",
        "--output", str(base.with_suffix(".txt")), str(source)
    ], check=True)
    tree = etree.parse(str(xml_path), etree.XMLParser(resolve_entities=False, no_network=True))
    root = tree.getroot()
    paragraphs = root.findall(".//Paragraph")
    text_by_paragraph = {p: paragraph_text(p) for p in paragraphs}
    blocks = []
    for index, paragraph in enumerate(paragraphs):
        text = text_by_paragraph[paragraph]
        if not text.strip():
            continue
        blocks.append({
            "block_id": f"p{index}", "source_file": source.name,
            "paragraph_id": paragraph.get("paragraph-id"),
            "xml_path": tree.getpath(paragraph),
            "cell_path": cell_path(paragraph), "text": text,
        })
    write_jsonl(output / f"{source.stem}.blocks.jsonl", blocks)
    (output / f"{source.stem}.full.txt").write_text(
        "\n".join(b["text"] for b in blocks) + "\n", encoding="utf-8"
    )

    tables = []
    paired_rows = []
    for table in root.findall(".//TableControl"):
        body = table.find("TableBody")
        if body is None:
            continue
        cells = []
        for cell in body.findall("./TableRow/TableCell"):
            cells.append({
                **{key: int(cell.get(key)) for key in ("row", "col", "rowspan", "colspan")},
                "xml_path": tree.getpath(cell),
                "text": "\n".join(text_by_paragraph[p] for p in cell.iter("Paragraph")
                                    if text_by_paragraph[p].strip()),
                "nested_table_ids": [t.get("table-id") for t in cell.iter("TableControl")],
            })
        table_id = table.get("table-id")
        tables.append({
            "table_id": table_id, "xml_path": tree.getpath(table),
            "parent_cells": cell_path(table),
            "rows": int(body.get("rows")), "cols": int(body.get("cols")), "cells": cells,
        })
        # Detect this document's regulation/guidance comparison tables by header,
        # rather than splitting every table or treating each row as an article.
        headers = {c["col"]: c["text"].replace(" ", "") for c in cells if c["row"] == 0}
        if headers.get(0) != "취업규칙(안)" or "작성시착안사항" not in headers.get(1, ""):
            continue
        for row in sorted({c["row"] for c in cells} - {0}):
            row_cells = [c for c in cells if c["row"] == row]
            regulation = "\n".join(c["text"] for c in row_cells if c["col"] == 0)
            guidance = "\n".join(c["text"] for c in row_cells if c["col"] == 1)
            if not regulation.strip() and not guidance.strip():
                continue
            paired_rows.append({
                "source_file": source.name, "table_id": table_id, "row": row,
                "regulation_template": regulation, "drafting_guidance": guidance,
                "cell_paths": [c["xml_path"] for c in row_cells],
            })
    (output / f"{source.stem}.tables.json").write_text(
        json.dumps(tables, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_jsonl(output / f"{source.stem}.paired_rows.jsonl", paired_rows)

    text_nodes = root.findall(".//Text")
    owned_nodes = sum(nearest(t, "Paragraph") is not None for t in text_nodes)
    if owned_nodes != len(text_nodes):
        raise ValueError("XML contains text outside paragraphs; review extraction before using it")
    # Verify each XML Text node has a single owner and reaches the intermediate output.
    xml_chars = sum(len(t.text or "") for t in text_nodes)
    nonempty_chars = sum(len(t.text or "") for t in text_nodes
                         if text_by_paragraph[nearest(t, "Paragraph")].strip())
    report = {
        "source_file": source.name, "xml_paragraphs": len(paragraphs),
        "nonempty_paragraphs": len(blocks), "tables": len(tables),
        "table_cells": sum(len(t["cells"]) for t in tables),
        "xml_text_characters": xml_chars,
        "xml_text_characters_in_nonempty_blocks": nonempty_chars,
        "plain_txt_characters": len(base.with_suffix(".txt").read_text(encoding="utf-8")),
        "structured_text_characters": sum(len(b["text"]) for b in blocks),
        "paired_rows_by_table": dict(Counter(r["table_id"] for r in paired_rows)),
        "limitations": [
            "XML text coverage is not a visual comparison against the original HWP.",
            "Images/equations are not OCRed; XML traversal order is not guaranteed visual reading order.",
            "Blocks include contents, forms, templates, guidance and annexes; do not embed all blindly.",
            "A paired row can contain multiple articles; it is not a final RAG chunk.",
            "Table cell text includes nested tables; avoid indexing both parent and nested copies.",
            "Page numbers and reference links have not been resolved.",
        ],
    }
    (output / f"{source.stem}.report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "output")
    args = parser.parse_args()
    extract(args.source.resolve(), args.output.resolve())
