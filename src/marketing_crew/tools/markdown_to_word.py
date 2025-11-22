import logging
from pathlib import Path
import os, shutil
import textwrap
import pypandoc
from crewai.tools import tool
from typing import Optional, Sequence

def _ensure_pandoc_env() -> None:
    """Ensure PYPANDOC_PANDOC points to a pandoc executable, downloading if needed."""
    if shutil.which("pandoc"):
        return
    downloaded = pypandoc.download_pandoc()
    if not downloaded:
        return
    p = Path(downloaded)
    pandoc_path = p if p.is_file() else p / ("pandoc.exe" if os.name == "nt" else "pandoc")
    os.environ["PYPANDOC_PANDOC"] = str(pandoc_path)

def _safe_mkdirs(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)

@tool("Markdown to Word Doc")
def markdown_to_word_doc(
    markdown: str,
    # output_path: str | None = None,
):
    """
    Convert Markdown string to a Word (.docx) using Pandoc, preserving Markdown features.

    - Uses GitHub-Flavored Markdown (GFM) with common extensions:
      tables, task lists, strikethrough, footnotes, $...$ math, smart quotes.
    - Optionally map styles via a Word template (reference_docx).
    - Optionally set resource_path so relative images are embedded properly.
    """
    # output_path = output_path or "./output/markdown_to_word.docx"
    output_path = "./output/markdown_to_word.docx"
    if not markdown or not markdown.strip():
        error = f"Markdown input is empty."
        logging.error("markdown_to_word_doc: ", error)
        return error
        return {
            "status": "error",
            "output_format": "docx",
            "output_path": output_path,
            "notes": "Markdown input is empty.",
            "raw": ""
        }

    if not output_path.lower().endswith(".docx"):
        error = f"output_path must end with .docx (Pandoc targets .docx, not legacy .doc): {output_path}"
        logging.error("markdown_to_word_doc: ", error)
        return error
        return {
            "status": "error",
            "output_format": "docx",
            "output_path": output_path,
            "notes": "output_path must end with .docx (Pandoc targets .docx, not legacy .doc).",
            "raw": ""
        }

    _ensure_pandoc_env()
    _safe_mkdirs(output_path)
    
    markdown = textwrap.dedent(markdown).lstrip("\ufeff").lstrip("\n")
    frmt = "gfm+smart+pipe_tables+strikeout+task_lists+tex_math_dollars+footnotes"

    try:
        pypandoc.convert_text(
            markdown,
            to="docx",
            format=frmt,
            outputfile=output_path,
        )
        return markdown
        # return {
        #     "status": "success",
        #     "output_format": "docx",
        #     "output_path": output_path,
        #     "notes": (
        #         "Converted with Pandoc using GFM extensions. "
        #         "If styles look off, provide a reference .docx to control Word styles."
        #     ),
        #     "raw": ""
        # }
    except Exception as e:
        error = f"Error converting Markdown to Word Doc: {e}"
        logging.error("markdown_to_word_doc: ", error)
        return error 
        # return {
        #     "status": "error",
        #     "output_format": "docx",
        #     "output_path": output_path,
        #     "notes": "Unexpected error during conversion.",
        #     "raw": repr(e)
        # }
