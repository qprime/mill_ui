# name: export_doc.py
# path: skills/living_truth_partner/export_doc.py
# role: Export LTD Markdown to PDF or DOCX via pandoc
# deps: dataclasses, pathlib, subprocess
# inputs: ProjectStore, Config, export kind
# outputs: ExportDoc.Result

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from skills.living_truth_partner.config import Config
from skills.living_truth_partner.project_store import ProjectStore

__all__ = ["ExportDoc"]


class ExportDoc:
    @dataclass(frozen=True)
    class Result:
        output_path: Path
        command: list[str]

    @staticmethod
    def run(store: ProjectStore, config: Config, kind: str) -> Result:
        kind_lower = kind.lower()
        if kind_lower not in {"pdf", "docx"}:
            raise ValueError(kind)
        if kind_lower == "pdf":
            template = config.templates / "pdf" / "default.latex"
            output = store.exports_root / f"{store.slug}.pdf"
            cmd = ["pandoc", str(store.doc_path), "-o", str(output), "--toc", "--number-sections"]
            if template.exists():
                cmd.extend(["--template", str(template)])
        else:
            template = config.templates / "docx" / "default.docx"
            output = store.exports_root / f"{store.slug}.docx"
            cmd = ["pandoc", str(store.doc_path), "-o", str(output)]
            if template.exists():
                cmd.extend(["--reference-doc", str(template)])
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(cmd, check=True)
        return ExportDoc.Result(output, cmd)
