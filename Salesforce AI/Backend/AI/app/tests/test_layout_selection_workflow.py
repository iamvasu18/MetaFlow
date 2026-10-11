"""Plan review choices for page layouts; development, single-process storage.

Choices never change profile assignments for existing layouts. Org XML is
retrieved again at deployment and checked against the reviewed layout.
"""
from copy import deepcopy
from functools import wraps
import hashlib
import json
from pathlib import Path
import tempfile
from threading import RLock
from uuid import uuid4
import xml.etree.ElementTree as ET

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from Backend.AI.app.services.page_layout_service import (
    PageLayoutService, Q, layout_path, new_layout, select_default_layout,
)
from Backend.AI.app.services.profile_fls_service import initialize_deployment_project


def layout_fingerprint(root):
    root = deepcopy(root)
    for node in root.iter():
        if node.text is not None and not node.text.strip():
            node.text = None
        node.tail = None
    return hashlib.sha256(ET.tostring(root)).hexdigest()


def affected_objects(plan):
    objects = {}
    for item in plan.items:
        if item.action != "CREATE":
            continue
        if item.metadataType == "CustomObject":
            objects.setdefault(item.fullName, {"new": False, "fields": []})["new"] = True
        elif item.metadataType == "CustomField":
            obj, separator, field = item.fullName.partition(".")
            if not separator or not field:
                raise ValueError("CustomField fullName must use Object.Field format.")
            objects.setdefault(obj, {"new": False, "fields": []})["fields"].append(field)
    return objects


def plan_fingerprint(plan):
    # Status and item approval change during approval; metadata intent must not.
    data = {"id": plan.id, "requirement": getattr(plan, "requirementId", None),
            "items": [{"id": i.id, "action": i.action, "type": i.metadataType,
                       "name": i.fullName, "config": i.config} for i in plan.items]}
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def section_options(root):
    result = []
    for index, section in enumerate(root.findall(Q("layoutSections"))):
        columns = section.findall(Q("layoutColumns"))
        style = section.findtext(Q("style"))
        if columns and style != "CustomLinks":
            result.append({"id": str(index), "label": section.findtext(Q("label")) or "(Unlabelled section)"})
    exact = [s for s in result if s["label"].strip().casefold() == "information"]
    matches = exact or [s for s in result if s["label"].strip().casefold().endswith(" information")
                        and s["label"].strip().casefold() not in {"system information", "additional information"}]
    return result, matches[0]["id"] if len(matches) == 1 else None


class LayoutChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fullName: str
    sectionId: str | None = None


class ObjectChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    object: str
    layouts: list[LayoutChoice] = Field(min_length=1)


class LayoutSelectionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshotId: str
    selections: list[ObjectChoice]


class LayoutSelectionWorkflow:
    def __init__(self, plan_store, project_root=".", target_org="AIOrg"):
        self.plan_store = plan_store
        self.project_root = Path(project_root)
        self.target_org = target_org
        self._states = {}
        self._lock = RLock()
        self.router = APIRouter(tags=["Page layout review"])
        self.router.add_api_route("/api/plans/{plan_id}/layout-options", self.options, methods=["GET"])
        self.router.add_api_route("/api/plans/{plan_id}/layout-selections", self.save, methods=["POST"])

    def locked(self, fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            with self._lock:
                return fn(*args, **kwargs)
        return wrapped

    def _plan(self, plan_id):
        plan = self.plan_store.get(plan_id)
        if plan is None:
            raise HTTPException(404, f"Plan not found: {plan_id}")
        return plan

    def _discover(self, plan):
        affected = affected_objects(plan)
        result = []
        if not affected:
            return result
        with tempfile.TemporaryDirectory(prefix="salesforce-layout-options-", ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            initialize_deployment_project(self.project_root, root)
            service = PageLayoutService(self.project_root, self.target_org)
            profile, known = service._retrieve(root)
            for obj, intent in sorted(affected.items()):
                if obj.endswith(("__kav", "__ka", "__mdt", "__x", "__e")):
                    raise ValueError(f"Automatic page layout placement is not supported for {obj}.")
                names = sorted(n for n in known if n.startswith(obj + "-"))
                created = intent["new"] and not names
                if not names and not created:
                    raise ValueError(f"No page layouts were retrieved for {obj}.")
                if created:
                    label = obj.removesuffix("__c").replace("__", "_")
                    names = [f"{obj}-{label} Layout"]
                try:
                    recommended = select_default_layout(profile, obj)
                except ValueError:
                    recommended = None
                layouts = []
                for name in names:
                    if created:
                        xml = new_layout(ET.Element(Q("CustomObject")))
                    else:
                        source = root / layout_path(name)
                        if not source.is_file():
                            raise ValueError(f"Layout was listed but not retrieved: {name}")
                        xml = ET.parse(source).getroot()
                        if xml.tag != Q("Layout"):
                            raise ValueError(f"Invalid Layout XML: {name}")
                    sections, default = section_options(xml)
                    layouts.append({"fullName": name, "created": created,
                                    "recommended": name == recommended,
                                    "sections": sections, "defaultSectionId": default,
                                    "fingerprint": None if created else layout_fingerprint(xml)})
                result.append({"object": obj, "fields": intent["fields"], "layouts": layouts})
        return result

    def _response(self, plan, state):
        unresolved = []
        for obj in state["objects"]:
            selected = state["selected"].get(obj["object"], [])
            if not selected:
                unresolved.append({"object": obj["object"], "reason": "SELECT_LAYOUTS"})
            else:
                for choice in selected:
                    if choice["sectionId"] is None and obj["fields"]:
                        unresolved.append({"object": obj["object"], "layout": choice["fullName"], "reason": "SELECT_SECTION"})
        objects = deepcopy(state["objects"])
        for obj in objects:
            for layout in obj["layouts"]:
                layout.pop("fingerprint", None)
        choices = [{"object": obj, "layouts": [{"fullName": c["fullName"], "sectionId": c["sectionId"]} for c in values]}
                   for obj, values in state["selected"].items()]
        return {"planId": plan.id, "targetOrg": self.target_org, "snapshotId": state["snapshotId"],
                "objects": objects, "selections": choices, "ready": not unresolved,
                "unresolved": unresolved, "readOnly": plan.status != "DRAFT"}

    def options(self, plan_id: str, refresh: bool = False):
        """Discover options before approval. refresh=true discards draft choices."""
        with self._lock:
            plan = self._plan(plan_id)
            state = self._states.get(plan_id)
            if refresh and plan.status != "DRAFT":
                raise HTTPException(409, "Approved/rejected layout choices cannot be refreshed. Create a new plan.")
            if state and state["planFingerprint"] != plan_fingerprint(plan):
                if plan.status != "DRAFT":
                    raise HTTPException(409, "Plan changed after layout review. Create a new plan.")
                state = None
            if state is None or refresh:
                if plan.status != "DRAFT":
                    raise HTTPException(409, "Review layout choices on a new DRAFT plan before approval.")
                try:
                    objects = self._discover(plan)
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from exc
                except (RuntimeError, OSError, ET.ParseError) as exc:
                    raise HTTPException(502, str(exc)) from exc
                selected = {}
                for obj in objects:
                    if len(obj["layouts"]) == 1:
                        layout = obj["layouts"][0]
                        selected[obj["object"]] = [dict(layout, sectionId=layout["defaultSectionId"])]
                state = {"snapshotId": str(uuid4()), "planFingerprint": plan_fingerprint(plan),
                         "objects": objects, "selected": selected}
                self._states[plan_id] = state
            return self._response(plan, state)

    def save(self, plan_id: str, request: LayoutSelectionsRequest):
        """Replace choices for supplied objects; retain other automatic choices."""
        with self._lock:
            plan = self._plan(plan_id)
            if plan.status != "DRAFT":
                raise HTTPException(409, "Layout choices can only change on a DRAFT plan.")
            state = self._states.get(plan_id)
            if not state or state["snapshotId"] != request.snapshotId or state["planFingerprint"] != plan_fingerprint(plan):
                raise HTTPException(409, "Layout options are missing or stale. GET layout-options again.")
            updated = deepcopy(state)
            objects = {obj["object"]: obj for obj in state["objects"]}
            seen = set()
            for choice in request.selections:
                if choice.object in seen or choice.object not in objects:
                    raise HTTPException(422, "Unknown or duplicate object selection.")
                seen.add(choice.object)
                available = {x["fullName"]: x for x in objects[choice.object]["layouts"]}
                values, names = [], set()
                for pick in choice.layouts:
                    if pick.fullName not in available or pick.fullName in names:
                        raise HTTPException(422, "Unknown or duplicate layout selection.")
                    names.add(pick.fullName)
                    layout = available[pick.fullName]
                    section = pick.sectionId if pick.sectionId is not None else layout["defaultSectionId"]
                    if section is not None and section not in {s["id"] for s in layout["sections"]}:
                        raise HTTPException(422, "Unknown sectionId for selected layout.")
                    values.append(dict(layout, sectionId=section))
                updated["selected"][choice.object] = values
            self._states[plan_id] = updated
            return self._response(plan, updated)

    def require(self, plan):
        """Approval/deployment gate; no org calls and no mutation of choices."""
        with self._lock:
            if not affected_objects(plan):
                return {}
            state = self._states.get(plan.id)
            if not state or state["planFingerprint"] != plan_fingerprint(plan):
                raise HTTPException(409, {"code": "LAYOUT_REVIEW_REQUIRED", "message": "GET layout-options and complete selections before approval."})
            response = self._response(plan, state)
            if not response["ready"]:
                raise HTTPException(409, {"code": "LAYOUT_SELECTION_REQUIRED", "unresolved": response["unresolved"]})
            return deepcopy(state["selected"])
