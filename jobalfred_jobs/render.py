"""Write the Markdown tables and JSON. Job text is untrusted, so it is escaped before output."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import links

DISCLAIMER = (
    "**Please confirm before you rely on this.** A posting saying it offers sponsorship is not a guarantee. "
    "Each row here quotes a posting that says so in its own words; JobAlfred never infers sponsorship and "
    "cannot see an employer's current policy. Confirm with the employer in writing that sponsorship applies "
    "to your role, your nationality and your country, before you resign, move or pay for anything. "
    "This is not immigration advice."
)
MAX_TABLE_BYTES = 450_000  # GitHub stops rendering long Markdown files around 512 KB


def md_cell(text: str) -> str:
    """Neutralise anything in a job title that could break out of a table cell."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return re.sub(r"([\\`*_\[\]<>|!])", r"\\\1", text)


def row(job: dict, spec: dict) -> str:
    cells = [md_cell(job["company"]), md_cell(job["title"]), md_cell(job["location"])]
    if spec.get("show_scope"):
        cells.append(md_cell(job.get("scope", "")))
    if spec.get("show_quote"):
        cells.append(md_cell(job.get("quote", "")))
    cells += [job["posted"] or "unknown", f"[Apply]({job['apply_url']})", f"[Fill with JobAlfred]({job['fill_url']})"]
    return "| " + " | ".join(cells) + " |"


def header(spec: dict) -> list[str]:
    cols = ["Company", "Role", "Location"]
    if spec.get("show_scope"):
        cols.append("Stated scope")
    if spec.get("show_quote"):
        cols.append("What the posting says")
    cols += ["Posted", "Apply", "Fill"]
    return ["| " + " | ".join(cols) + " |", "|" + " --- |" * len(cols)]


def table_md(spec: dict, jobs: list[dict], built: str, settings: dict) -> str:
    banner = links.install_link(settings, spec["slug"], spec["campaign"], "banner")
    lines = [f"# {spec['title']}", "", spec["intro"], ""]
    if spec.get("show_quote"):
        lines += [f"> {DISCLAIMER}", ""]
    search = f"https://jobalfred.com/jobs/?utm_source=github&utm_medium=job_list&utm_campaign={spec['campaign']}"
    lines += [f"**Looking for more? [Search over 1.5 million jobs on jobalfred.com]({search}).**", ""]
    lines += [f"**{len(jobs)} open roles.** Refreshed {built}. Closed roles are removed on every run.", "",
              f"[Fill applications with JobAlfred]({banner}): a free Chrome extension that fills the form from "
              "your CV. You check every answer and press Submit yourself.", ""]
    body, size, shown = [], 0, 0
    for job in jobs:
        line = row(job, spec)
        size += len(line.encode()) + 1
        if size > MAX_TABLE_BYTES:
            break
        body.append(line)
        shown += 1
    if shown < len(jobs):
        lines += [f"Showing the {shown} newest. All {len(jobs)} are in [the JSON](../data/{spec['slug']}.json).", ""]
    lines += header(spec) + body + [""]
    return "\n".join(lines)


def public_record(job: dict) -> dict:
    return {k: v for k, v in job.items() if not k.startswith("_")}


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")


def readme_block(lists: list[dict], built: str) -> str:
    lines = [f"Refreshed {built}.", "", "| List | Open roles | Table | JSON |", "| --- | --- | --- | --- |"]
    for spec in lists:
        lines.append(f"| {spec['title']} | {spec['count']} | [Open](lists/{spec['slug']}.md) "
                     f"| [{spec['slug']}.json](data/{spec['slug']}.json) |")
    return "\n".join(lines)


def update_readme(path: Path, block: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    new = re.sub(r"(<!-- counts:start -->\n).*?(\n<!-- counts:end -->)",
                 lambda m: m.group(1) + block + m.group(2), text, flags=re.S)
    path.write_text(new, encoding="utf-8")
