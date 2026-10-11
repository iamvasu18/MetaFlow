from __future__ import annotations

import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

from Backend.AI.app.services.apex_validator import validate_apex_source

SALESFORCE_METADATA_NS = "http://soap.sforce.com/2006/04/metadata"
DEFAULT_API_VERSION = "67.0"


def _api_version(project_root: str | Path) -> str:
    project = Path(project_root) / "sfdx-project.json"
    if project.is_file():
        try:
            data = json.loads(project.read_text(encoding="utf-8"))
            value = data.get("sourceApiVersion")
            if re.fullmatch(r'\d{2,3}\.0', str(value)) and float(value) >= 45:
                return str(value)
            raise ValueError('Invalid sourceApiVersion in sfdx-project.json.')
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError('Cannot read sfdx-project.json.') from exc
    return DEFAULT_API_VERSION


def generate_apex(item, project_root: str | Path) -> Path:
    metadata_type = item.metadataType
    config = item.config or {}
    errors, _warnings = validate_apex_source(metadata_type, item.fullName, config)
    if errors:
        raise ValueError("Apex validation failed: " + "; ".join(errors))

    root = Path(project_root) / "force-app" / "main" / "default"
    if metadata_type == "ApexClass":
        folder = root / "classes"
        source_suffix = ".cls"
        meta_suffix = ".cls-meta.xml"
        meta_type = "ApexClass"
    elif metadata_type == "ApexTrigger":
        folder = root / "triggers"
        source_suffix = ".trigger"
        meta_suffix = ".trigger-meta.xml"
        meta_type = "ApexTrigger"
    else:
        raise ValueError(f"Unsupported Apex metadata type: {metadata_type}")

    from Backend.AI.app.services.metadata_safety import component_path, safe_source_target
    source_path = safe_source_target(project_root, component_path(metadata_type, item.fullName).as_posix())
    meta_path = safe_source_target(project_root, source_path.relative_to(Path(project_root).resolve()).as_posix() + "-meta.xml")
    source_path.parent.mkdir(parents=True, exist_ok=True)
    body = str(config["body"]).rstrip() + "\n"
    source_path.write_text(body, encoding="utf-8")
    meta_path.write_text(
        f'''<?xml version="1.0" encoding="UTF-8"?>\n<{meta_type} xmlns="{SALESFORCE_METADATA_NS}">\n    <apiVersion>{escape(_api_version(project_root))}</apiVersion>\n    <status>Active</status>\n</{meta_type}>\n''',
        encoding="utf-8",
    )
    return source_path
