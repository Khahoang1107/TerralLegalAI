"""Persistent storage paths for uploaded form templates."""
from __future__ import annotations

import os
import shutil


TEMPLATE_DIR = os.getenv("FORM_TEMPLATE_DIR", os.path.join("data", "templates"))
LEGACY_TEMPLATE_DIR = os.path.join("backend", "data", "templates")


def writable_template_path(form_id: str) -> str:
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    return os.path.join(TEMPLATE_DIR, f"{form_id}.docx")


def resolve_template_path(form_id: str, *, allow_default: bool = False) -> str | None:
    """Resolve a template and migrate a repository-era file into the volume."""
    destination = writable_template_path(form_id)
    if os.path.exists(destination):
        return destination

    legacy = os.path.join(LEGACY_TEMPLATE_DIR, f"{form_id}.docx")
    if os.path.exists(legacy):
        shutil.copy2(legacy, destination)
        return destination

    if allow_default:
        persistent_default = os.path.join(TEMPLATE_DIR, "default.docx")
        if os.path.exists(persistent_default):
            return persistent_default
        legacy_default = os.path.join(LEGACY_TEMPLATE_DIR, "default.docx")
        if os.path.exists(legacy_default):
            shutil.copy2(legacy_default, persistent_default)
            return persistent_default
    return None
