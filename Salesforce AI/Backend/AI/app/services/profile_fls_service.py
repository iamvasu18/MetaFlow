"""Build a narrow System Administrator profile overlay for CREATE fields."""
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET

NS = "http://soap.sforce.com/2006/04/metadata"
API_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
ET.register_namespace("", NS)


def component_path(metadata_type, full_name):
    """Resolve only supported components; reject traversal before generation."""
    parts = full_name.split(".")
    expected = 1 if metadata_type == "CustomObject" else 2
    if metadata_type not in {"CustomObject", "CustomField", "ValidationRule"}:
        raise ValueError(f"Unsupported CREATE metadata type: {metadata_type}")
    if len(parts) != expected or any(not API_NAME.fullmatch(p) for p in parts):
        raise ValueError(f"Invalid {metadata_type} fullName: {full_name}")
    base = Path("force-app/main/default/objects") / parts[0]
    if metadata_type == "CustomObject":
        return base / f"{parts[0]}.object-meta.xml"
    folder, suffix = ("fields", "field-meta.xml") if metadata_type == "CustomField" else ("validationRules", "validationRule-meta.xml")
    return base / folder / f"{parts[1]}.{suffix}"


def validate_create_specification(plan, specification):
    """Check the stored spec still belongs to the approved CREATE items."""
    if plan.status != "APPROVED" or specification.planId != plan.id:
        raise ValueError("An approved plan and matching metadata specification are required.")
    if specification.validationIssues:
        raise ValueError("Metadata specification contains validation issues.")
    expected = {}
    for item in plan.items:
        if item.action != "CREATE":
            continue
        if item.approval != "APPROVED":
            raise ValueError(f"Plan item is not approved: {item.id}")
        component_path(item.metadataType, item.fullName)
        expected[item.id] = (item.metadataType, item.fullName)
    actual = {}
    for item in specification.metadata:
        if item.action != "CREATE":
            raise ValueError("CREATE deployment cannot include UPDATE or DELETE specifications.")
        component_path(item.metadataType, item.fullName)
        if item.itemId in actual:
            raise ValueError(f"Duplicate specification item: {item.itemId}")
        actual[item.itemId] = (item.metadataType, item.fullName)
    if not actual or actual != expected:
        raise ValueError("Stored CREATE specification does not match approved CREATE plan items. Regenerate metadata.")


def initialize_deployment_project(source_root, deployment_root):
    """Keep the project's API version/namespace, but stage one source package."""
    source = Path(source_root) / "sfdx-project.json"
    if not source.is_file():
        raise ValueError("Run the backend from the Salesforce project root containing sfdx-project.json.")
    config = json.loads(source.read_text(encoding="utf-8"))
    staged = {key: config[key] for key in ("sourceApiVersion", "namespace", "sfdcLoginUrl") if key in config}
    staged["packageDirectories"] = [{"path": "force-app", "default": True}]
    root = Path(deployment_root)
    (root / "force-app/main/default").mkdir(parents=True, exist_ok=True)
    (root / "sfdx-project.json").write_text(json.dumps(staged, indent=2), encoding="utf-8")


class SystemAdministratorFLSService:
    """Admin is the standard System Administrator metadata profile name.

    Writes only this deployment's fieldPermissions, never copies a whole
    local profile. Existing settings absent from the overlay are preserved.
    """
    def __init__(self, project_root="."):
        self.project_root = Path(project_root).resolve()

    def generate(self, specification):
        entries = []
        skipped = []
        for item in specification.metadata:
            if item.action != "CREATE" or item.metadataType != "CustomField":
                continue
            path = self.project_root / component_path(item.metadataType, item.fullName)
            root = ET.parse(path).getroot()
            if root.tag != f"{{{NS}}}CustomField":
                raise ValueError(f"Invalid field XML: {item.fullName}")
            def value(name):
                return (root.findtext(f"{{{NS}}}{name}") or "").strip()
            if value("fullName") != item.fullName.split(".", 1)[1]:
                raise ValueError(f"Field XML name does not match specification: {item.fullName}")
            kind = value("type")
            if not kind:
                raise ValueError(f"Field XML is missing type: {item.fullName}")
            # Universally required and master-detail fields are not permissionable.
            if value("required").lower() == "true" or kind == "MasterDetail":
                skipped.append({"field": item.fullName, "reason": "Required/master-detail field: explicit FLS is not deployable."})
                continue
            calculated = root.find(f"{{{NS}}}formula") is not None
            editable = not calculated and kind not in {"Summary", "AutoNumber"}
            entries.append({"field": item.fullName, "readable": True, "editable": editable})
        entries.sort(key=lambda entry: entry["field"])
        result = {"profile": "Admin", "profileLabel": "System Administrator", "fieldPermissions": entries, "skippedFields": skipped, "generatedFiles": []}
        if not entries:
            return result
        profile = ET.Element(f"{{{NS}}}Profile")
        for entry in entries:
            permission = ET.SubElement(profile, f"{{{NS}}}fieldPermissions")
            for key in ("editable", "field", "readable"):
                val = entry[key]
                ET.SubElement(permission, f"{{{NS}}}{key}").text = str(val).lower() if isinstance(val, bool) else val
        relative = Path("force-app/main/default/profiles/Admin.profile-meta.xml")
        path = self.project_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        ET.indent(profile, space="    ")
        ET.ElementTree(profile).write(path, encoding="utf-8", xml_declaration=True)
        # Verify the serialized artifact contains exactly the intended grants.
        parsed = ET.parse(path).getroot()
        actual = [{"field": p.findtext(f"{{{NS}}}field"), "readable": p.findtext(f"{{{NS}}}readable") == "true", "editable": p.findtext(f"{{{NS}}}editable") == "true"} for p in parsed]
        if actual != entries or any(p.tag != f"{{{NS}}}fieldPermissions" for p in parsed):
            raise ValueError("Generated Admin FLS XML does not match intended permissions.")
        result["generatedFiles"] = [str(relative)]
        return result
