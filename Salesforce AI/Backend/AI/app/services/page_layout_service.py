"""Add CREATE fields to reviewed layouts and sections.

Retrieve into a separate project: never overwrite generated fields or FLS.
Only selected layouts and a narrow Admin overlay enter the deployment.
"""
from Backend.AI.app.services.metadata_safety import safe_source_target
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from Backend.AI.app.services.profile_fls_service import (
    NS, API_NAME, component_path, initialize_deployment_project,
)

Q = lambda name: f"{{{NS}}}{name}"
PROFILE_PATH = Path("force-app/main/default/profiles/Admin.profile-meta.xml")


def layout_path(full_name):
    object_name, separator, label = full_name.partition("-")
    if (not separator or not API_NAME.fullmatch(object_name) or not label
            or any(c in full_name for c in '/\\:*?"<>|')
            or any(ord(c) < 32 for c in full_name) or label.endswith((".", " "))):
        raise ValueError(f"Unsafe or unsupported layout name: {full_name}")
    return Path("force-app/main/default/layouts") / f"{full_name}.layout-meta.xml"


def write_xml(root, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="    ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def select_default_layout(profile, object_name):
    assignments = [a for a in profile.findall(Q("layoutAssignments"))
                   if (a.findtext(Q("layout")) or "").startswith(object_name + "-")]
    defaults = [v.findtext(Q("recordType"))
                for v in profile.findall(Q("recordTypeVisibilities"))
                if v.findtext(Q("default")) == "true"
                and (v.findtext(Q("recordType")) or "").startswith(object_name + ".")]
    if len(defaults) > 1:
        raise ValueError(f"Multiple Admin default record types found for {object_name}.")
    if defaults:
        selected = [a for a in assignments if a.findtext(Q("recordType")) == defaults[0]]
    else:
        selected = [a for a in assignments if not a.findtext(Q("recordType"))]
    names = {a.findtext(Q("layout")) for a in selected}
    if not names and not defaults:
        # Safe only when every assignment points to the same layout.
        names = {a.findtext(Q("layout")) for a in assignments}
    if len(names) != 1:
        raise ValueError(f"Cannot uniquely resolve the System Administrator default layout for {object_name}. Check its page layout assignments.")
    return names.pop()


def add_fields(layout, field_roots, section_id=None):
    if layout.tag != Q("Layout"):
        raise ValueError("Retrieved XML is not a Salesforce Layout.")
    existing = {node.text for node in layout.findall(f"{Q('layoutSections')}/{Q('layoutColumns')}/{Q('layoutItems')}/{Q('field')}")}
    pending = [(name, root) for name, root in field_roots if name not in existing]
    if not pending:
        return [], [name for name, _ in field_roots]
    sections = layout.findall(Q("layoutSections"))
    exact = [s for s in sections if (s.findtext(Q("label")) or "").strip().casefold() == "information"]
    candidates = exact or [s for s in sections if (s.findtext(Q("label")) or "").strip().casefold().endswith(" information")
                            and (s.findtext(Q("label")) or "").strip().casefold() not in {"system information", "additional information"}]
    if section_id is not None:
        candidates = [s for index, s in enumerate(sections) if str(index) == section_id]
    if len(candidates) != 1:
        raise ValueError("Layout must have one identifiable Information section; no section was changed. Rename/select the intended section before deploying.")
    section = candidates[0]
    columns = section.findall(Q("layoutColumns"))
    if not columns:
        raise ValueError("The existing Information section has no layout columns.")
    for name, field in pending:
        kind = field.findtext(Q("type"))
        calculated = field.find(Q("formula")) is not None or kind in {"Summary", "AutoNumber"}
        required = field.findtext(Q("required")) == "true" or kind == "MasterDetail"
        behavior = "Readonly" if calculated else "Required" if required else "Edit"
        column = min(columns, key=lambda c: len(c.findall(Q("layoutItems"))))
        item = ET.Element(Q("layoutItems"))
        ET.SubElement(item, Q("behavior")).text = behavior
        ET.SubElement(item, Q("field")).text = name
        # layoutItems must precede reserved (when present).
        reserved = column.find(Q("reserved"))
        column.insert(list(column).index(reserved) if reserved is not None else len(column), item)
        existing.add(name)
    return [name for name, _ in pending], [name for name, _ in field_roots if name not in {n for n, _ in pending}]


def new_layout(object_root):
    root = ET.Element(Q("Layout"))
    section = ET.SubElement(root, Q("layoutSections"))
    for key, value in [("customLabel", "true"), ("detailHeading", "true"), ("editHeading", "true"), ("label", "Information")]:
        ET.SubElement(section, Q(key)).text = value
    column = ET.SubElement(section, Q("layoutColumns"))
    item = ET.SubElement(column, Q("layoutItems"))
    name_field = object_root.find(Q("nameField"))
    auto = name_field is not None and name_field.findtext(Q("type")) == "AutoNumber"
    ET.SubElement(item, Q("behavior")).text = "Readonly" if auto else "Required"
    ET.SubElement(item, Q("field")).text = "Name"
    ET.SubElement(section, Q("layoutColumns"))
    ET.SubElement(section, Q("style")).text = "TwoColumnsTopToBottom"
    return root


class PageLayoutService:
    def __init__(self, project_root=".", target_org="AIOrg"):
        self.project_root = Path(project_root).resolve()
        self.target_org = target_org

    def _cli(self, root, arguments):
        executable = shutil.which("sf")
        if not executable:
            raise RuntimeError("Salesforce CLI 'sf' is not installed or is not on PATH.")
        try:
            result = subprocess.run([executable, *arguments, "--target-org", self.target_org, "--json"], cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1920, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"Salesforce layout retrieval could not finish: {exc}") from exc
        try:
            data = json.loads(result.stdout)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Salesforce layout retrieval returned invalid JSON.") from exc
        if result.returncode or data.get("status") != 0:
            raise RuntimeError("Salesforce layout retrieval failed: " + str(data.get("message") or data.get("result") or result.stderr))
        return data.get("result")

    def _retrieve(self, root, objects=None):
        from Backend.AI.app.services.salesforce_metadata_api import owned_metadata_api
        config=json.loads((root/'sfdx-project.json').read_text(encoding='utf-8'))
        api=owned_metadata_api(self.target_org,config.get('sourceApiVersion'))
        if api:
            members={}
            for kind in ('Layout','RecordType'):
                rows=api.list_metadata(kind)
                members[kind]=sorted({r['fullName'] for r in rows if objects is None or any(r['fullName'].startswith(obj+('-' if kind=='Layout' else '.')) for obj in objects)})
            members['Profile']=['Admin']
            api.retrieve_layouts(members,root)
            return ET.parse(root/PROFILE_PATH).getroot(),set(members['Layout'])
        # Retrieve all layout assignments, but NEVER deploy all retrieved files.
        # RecordTypes and Layouts must accompany Profile in the same retrieve.
        members = {}
        for kind in ("Layout", "RecordType"):
            records = self._cli(root, ["org", "list", "metadata", "--metadata-type", kind])
            if not isinstance(records, list):
                raise RuntimeError(f"Unexpected {kind} discovery response.")
            members[kind] = sorted({r["fullName"] for r in records if objects is None or any(r["fullName"].startswith(obj + ("-" if kind == "Layout" else ".")) for obj in objects)})
        members["Profile"] = ["Admin"]
        package = ET.Element(Q("Package"))
        for kind, names in members.items():
            if names:
                node = ET.SubElement(package, Q("types"))
                for name in names:
                    ET.SubElement(node, Q("members")).text = name
                ET.SubElement(node, Q("name")).text = kind
        config = json.loads((root / "sfdx-project.json").read_text(encoding="utf-8"))
        version = config.get("sourceApiVersion")
        if not version:
            raise ValueError("sfdx-project.json must contain sourceApiVersion for layout retrieval.")
        ET.SubElement(package, Q("version")).text = str(version)
        manifest = root / "layout-retrieve.xml"
        write_xml(package, manifest)
        result = self._cli(root, ["project", "retrieve", "start", "--manifest", str(manifest), "--wait", "30"])
        if not isinstance(result, dict) or result.get("success") is not True or result.get("done") is not True:
            raise RuntimeError("Salesforce layout retrieval did not complete successfully.")
        profile = root / PROFILE_PATH
        if not profile.is_file():
            raise RuntimeError("Salesforce did not return the Admin profile.")
        return ET.parse(profile).getroot(), set(members["Layout"])

    def generate(self, specification, selections=None):
        fields = {}
        new_objects = set()
        for item in specification.metadata:
            if item.action != "CREATE":
                continue
            if item.metadataType == "CustomObject":
                new_objects.add(item.fullName)
                fields.setdefault(item.fullName, [])
            elif item.metadataType == "CustomField":
                object_name, name = item.fullName.split(".", 1)
                if object_name.endswith(("__kav", "__ka", "__mdt", "__x", "__e")):
                    raise ValueError(f"Automatic page layout placement is not supported for {object_name}.")
                field = ET.parse(self.project_root / component_path(item.metadataType, item.fullName)).getroot()
                if field.tag != Q("CustomField") or field.findtext(Q("fullName")) != name or not field.findtext(Q("type")):
                    raise ValueError(f"Invalid generated field: {item.fullName}")
                fields.setdefault(object_name, []).append((name, field))
        report = {"profile": "Admin", "section": "Selected per layout" if selections is not None else "Information", "layouts": [], "generatedFiles": []}
        if not fields:
            return report
        with tempfile.TemporaryDirectory(prefix="salesforce-layout-retrieve-", ignore_cleanup_errors=True) as directory:
            retrieval = Path(directory)
            initialize_deployment_project(self.project_root, retrieval)
            if set(fields)<=new_objects:
                # There are no existing layout assignments for CREATE-only objects.
                # Emit only new assignments; existing Admin assignments remain untouched.
                profile,known_layouts=ET.Element(Q('Profile')),set()
            else:
                profile, known_layouts = self._retrieve(retrieval, objects=set(fields) - new_objects)
            if profile.tag != Q("Profile"):
                raise ValueError("Retrieved Admin XML is not a Profile.")
            assignments = [deepcopy(a) for a in profile.findall(Q("layoutAssignments"))]
            for object_name, roots in sorted(fields.items()):
                object_layouts = {n for n in known_layouts if n.startswith(object_name + "-")}
                created = object_name in new_objects and not object_layouts
                if created:
                    # Object API suffix belongs before the hyphen, not in the
                    # layout name where double underscores imply a namespace.
                    layout_label = object_name.removesuffix("__c").replace("__", "_")
                    name = f"{object_name}-{layout_label} Layout"
                    layout = new_layout(ET.parse(self.project_root / component_path("CustomObject", object_name)).getroot())
                    assignment = ET.Element(Q("layoutAssignments"))
                    ET.SubElement(assignment, Q("layout")).text = name
                    assignments.append(assignment)
                    selected = [{"fullName": name, "sectionId": "0"}]
                else:
                    if selections is None:
                        if len(object_layouts) != 1:
                            raise ValueError(f"Select layouts for {object_name} before deployment.")
                        selected = [{"fullName": next(iter(object_layouts))}]
                    else:
                        selected = selections.get(object_name, [])
                        if not selected:
                            raise ValueError(f"No approved layout selection for {object_name}.")
                for choice in selected:
                    name = choice["fullName"]
                    if not created:
                        if choice.get("created"):
                            raise ValueError(f"Layout availability changed for {object_name}; review a new plan.")
                        source = retrieval / layout_path(name)
                        if name not in object_layouts or not source.is_file():
                            raise ValueError(f"Selected layout was not retrieved: {name}")
                        layout = ET.parse(source).getroot()
                        if choice.get("fingerprint"):
                            from Backend.AI.app.services.layout_selection_service import layout_fingerprint
                            if layout_fingerprint(layout) != choice["fingerprint"]:
                                raise ValueError(f"Layout changed since review: {name}. Create a new plan and review layout options again.")
                    elif selections is not None:
                        expected = selections.get(object_name, [])
                        if len(expected) != 1 or expected[0]["fullName"] != name or not expected[0].get("created"):
                            raise ValueError(f"Layout availability changed for {object_name}; review a new plan.")
                    added, skipped = add_fields(layout, roots, choice.get("sectionId"))
                    relative = layout_path(name)
                    write_xml(layout, safe_source_target(self.project_root, relative.as_posix()))
                    report["generatedFiles"].append(relative.as_posix())
                    report["layouts"].append({"fullName": name, "object": object_name, "created": created, "sectionId": choice.get("sectionId"), "addedFields": added, "alreadyPresent": skipped})
            # Preserve every retrieved assignment, but no unrelated permissions.
            profile_path = safe_source_target(self.project_root, PROFILE_PATH.as_posix())
            overlay = ET.parse(profile_path).getroot() if profile_path.exists() else ET.Element(Q("Profile"))
            if any(child.tag != Q("fieldPermissions") for child in overlay):
                raise ValueError("Expected a fresh FLS-only Admin overlay before layout generation.")
            for assignment in assignments:
                overlay.append(assignment)
            write_xml(overlay, profile_path)
            report["generatedFiles"].append(PROFILE_PATH.as_posix())
        return report
