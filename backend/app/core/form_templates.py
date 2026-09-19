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


def _candidate_search_dirs() -> list[str]:
    dirs = []
    if os.getenv("FORM_TEMPLATE_DIR"):
        dirs.append(os.getenv("FORM_TEMPLATE_DIR"))
    dirs.extend([
        TEMPLATE_DIR,
        LEGACY_TEMPLATE_DIR,
        os.path.join("data", "templates"),
        os.path.join("backend", "data", "templates"),
        os.path.join("data", "uploaded"),
        os.path.join("backend", "data", "uploaded"),
    ])
    seen = set()
    result = []
    for d in dirs:
        norm = os.path.normpath(os.path.abspath(d))
        if norm not in seen and os.path.isdir(norm):
            seen.add(norm)
            result.append(norm)
    return result


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
    search_dirs = _candidate_search_dirs()

    for directory in search_dirs:
        try:
            entries = os.listdir(directory)
        except OSError:
            continue
        for filename in entries:
            if not filename.lower().endswith(".docx") or filename in {"default.docx", "sample.docx"}:
                continue
            candidate = os.path.join(directory, filename)
            text, variables = _document_signature(candidate)
            overlap = len(expected_keys & variables)
            title_hits = sum(token in text for token in name_tokens)

            # Match either variable overlap or strong title tokens (e.g. "bien", "dong")
            match_condition = (
                (overlap >= 2)
                or (overlap >= 1 and title_hits >= 1)
                or (title_hits >= min(2, len(name_tokens)) and title_hits >= 2)
            )
            if not match_condition:
                continue

            score = overlap * 100 + title_hits * 10
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

    # Check all known template directories for {form_id}.docx
    for d in [LEGACY_TEMPLATE_DIR, TEMPLATE_DIR, os.path.join("data", "templates"), os.path.join("backend", "data", "templates")]:
        candidate = os.path.join(d, f"{form_id}.docx")
        if os.path.exists(candidate) and not _is_default_template(candidate) and _is_valid_docx(candidate):
            _copy_atomic(candidate, destination)
            return destination

    recovered = _recover_legacy_template(
        destination,
        expected_fields=expected_fields,
        form_name=form_name,
    )
    if recovered:
        return recovered

    # If allowed, fall back to default template
    if allow_default:
        for d in [TEMPLATE_DIR, LEGACY_TEMPLATE_DIR, os.path.join("data", "templates"), os.path.join("backend", "data", "templates")]:
            def_path = os.path.join(d, "default.docx")
            if os.path.exists(def_path):
                return def_path
    return None
