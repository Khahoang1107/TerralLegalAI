"""Persistent storage paths for uploaded form templates."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import unicodedata
import zipfile


TEMPLATE_DIR = os.getenv("FORM_TEMPLATE_DIR", os.path.join("data", "templates"))
LEGACY_TEMPLATE_DIR = os.path.join("backend", "data", "templates")


def writable_template_path(form_id: str) -> str:
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    return os.path.join(TEMPLATE_DIR, f"{form_id}.docx")


def _copy_atomic(source: str, destination: str) -> None:
    """Replace a template only after a complete copy exists beside it."""
    directory = os.path.dirname(destination) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".template-", suffix=".docx", dir=directory)
    os.close(fd)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFD", (value or "").replace("Đ", "D").replace("đ", "d"))
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", "".join(
            char for char in value if unicodedata.category(char) != "Mn"
        ).lower()).split()
    )


def _document_signature(path: str) -> tuple[str, set[str]]:
    """Read searchable text and Jinja variable names without modifying DOCX."""
    try:
        with zipfile.ZipFile(path) as archive:
            xml = " ".join(
                archive.read(name).decode("utf-8", errors="ignore")
                for name in archive.namelist()
                if name.endswith(".xml")
            )
        text = _normalize(re.sub(r"<[^>]+>", " ", xml))
        variables = set(re.findall(r"\{\{\s*([A-Za-z_]\w*)", xml))
        return text, variables
    except (OSError, zipfile.BadZipFile):
        return "", set()


def _is_valid_docx(path: str) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return "word/document.xml" in archive.namelist()
    except (OSError, zipfile.BadZipFile):
        return False


def _is_default_template(path: str) -> bool:
    text, variables = _document_signature(path)
    return (
        "bieu mau dien thong tin" in text
        and variables.issubset({"ho_ten", "cmnd", "dia_chi", "loai_thu_tuc"})
    )


def _recover_legacy_template(
    destination: str,
    *,
    expected_fields: list[dict] | None,
    form_name: str | None,
) -> str | None:
    expected_keys = {
        str(field.get("key"))
        for field in (expected_fields or [])
        if isinstance(field, dict) and field.get("key")
    }
    name_tokens = {
        token for token in _normalize(form_name or "").split()
        if len(token) >= 3 and token not in {"don", "mau", "so"}
    }
    best: tuple[int, str] | None = None
    if not os.path.isdir(LEGACY_TEMPLATE_DIR):
        return None

    for filename in os.listdir(LEGACY_TEMPLATE_DIR):
        if not filename.lower().endswith(".docx") or filename in {"default.docx", "sample.docx"}:
            continue
        candidate = os.path.join(LEGACY_TEMPLATE_DIR, filename)
        text, variables = _document_signature(candidate)
        overlap = len(expected_keys & variables)
        title_hits = sum(token in text for token in name_tokens)
        # Require both the same document subject and several matching field
        # bindings before repairing a missing/corrupt persistent template.
        if overlap < 3 or title_hits < min(3, len(name_tokens)):
            continue
        score = overlap * 100 + title_hits
        if best is None or score > best[0]:
            best = (score, candidate)

    if not best:
        return None
    _copy_atomic(best[1], destination)
    return destination


def resolve_template_path(
    form_id: str,
    *,
    allow_default: bool = False,
    expected_fields: list[dict] | None = None,
    form_name: str | None = None,
) -> str | None:
    """Resolve a template and migrate a repository-era file into the volume."""
    destination = writable_template_path(form_id)
    if (
        os.path.exists(destination)
        and _is_valid_docx(destination)
        and not _is_default_template(destination)
    ):
        return destination

    legacy = os.path.join(LEGACY_TEMPLATE_DIR, f"{form_id}.docx")
    if os.path.exists(legacy) and not _is_default_template(legacy):
        _copy_atomic(legacy, destination)
        return destination

    recovered = _recover_legacy_template(
        destination,
        expected_fields=expected_fields,
        form_name=form_name,
    )
    if recovered:
        return recovered

    # A configured form must never be rendered on the generic fallback: its
    # saved zones would appear over an unrelated page and could be saved back
    # accidentally. The default remains available only to metadata-free
    # legacy callers.
    if allow_default and not expected_fields and not form_name:
        persistent_default = os.path.join(TEMPLATE_DIR, "default.docx")
        if os.path.exists(persistent_default):
            return persistent_default
        legacy_default = os.path.join(LEGACY_TEMPLATE_DIR, "default.docx")
        if os.path.exists(legacy_default):
            _copy_atomic(legacy_default, persistent_default)
            return persistent_default
    return None
