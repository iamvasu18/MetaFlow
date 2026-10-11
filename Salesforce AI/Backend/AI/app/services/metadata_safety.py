"""Portable metadata identities and contained source paths, checked before writes."""
import re
from pathlib import Path, PurePosixPath

API_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)
_ROOT = ("force-app", "main", "default")
_TYPES = {"CustomObject", "CustomField", "ValidationRule", "Flow", "ApexClass", "ApexTrigger", "LightningComponentBundle"}


def validate_component_name(metadata_type, full_name):
    if metadata_type not in _TYPES:
        raise ValueError(f"Unsupported metadata type: {metadata_type}")
    if not isinstance(full_name, str):
        raise ValueError("Metadata fullName must be a string.")
    parts = full_name.split(".")
    expected = 2 if metadata_type in {"CustomField", "ValidationRule"} else 1
    if len(parts) != expected or any(not API_NAME.fullmatch(p) or len(p) > 200 or _RESERVED.match(p) for p in parts):
        raise ValueError(f"Invalid {metadata_type} fullName: {full_name!r}")
    if metadata_type == "LightningComponentBundle" and (not full_name[0].islower() or "__" in full_name or full_name.endswith("_")):
        raise ValueError("Invalid LightningComponentBundle fullName.")
    return parts


def source_relative_path(value):
    # Reject ambiguous Windows paths even when the server runs on Linux.
    if not isinstance(value, str) or not value or any(c in value for c in "\\:\x00"):
        raise ValueError("Invalid generated source path.")
    parts = value.split("/")
    if tuple(parts[:3]) != _ROOT or len(parts) < 5 or any(
        p in {"", ".", ".."} or p.endswith((" ", ".")) or _RESERVED.match(p)
        or any(ord(c) < 32 or c in '<>"|?*' for c in p) for p in parts
    ):
        raise ValueError("Invalid generated source path.")
    return PurePosixPath(value)


def safe_source_target(project_root, relative_path):
    relative = source_relative_path(relative_path)
    root = Path(project_root).resolve()
    target = root.joinpath(*relative.parts)
    # Reject symlink aliases too: they could point at unrelated source inside root.
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("Generated source paths cannot contain symlinks.")
    if not target.resolve().is_relative_to(root):
        raise ValueError("Generated source path escapes the project root.")
    return target


def component_path(metadata_type, full_name):
    parts = validate_component_name(metadata_type, full_name)
    folders = {"Flow": ("flows", ".flow-meta.xml"), "ApexClass": ("classes", ".cls"), "ApexTrigger": ("triggers", ".trigger")}
    if metadata_type in folders:
        folder, suffix = folders[metadata_type]
        return Path("force-app/main/default") / folder / (full_name + suffix)
    if metadata_type == "LightningComponentBundle":
        return Path("force-app/main/default/lwc") / full_name / (full_name + ".js")
    base = Path("force-app/main/default/objects") / parts[0]
    if metadata_type == "CustomObject":
        return base / (parts[0] + ".object-meta.xml")
    folder, suffix = ("fields", ".field-meta.xml") if metadata_type == "CustomField" else ("validationRules", ".validationRule-meta.xml")
    return base / folder / (parts[1] + suffix)
