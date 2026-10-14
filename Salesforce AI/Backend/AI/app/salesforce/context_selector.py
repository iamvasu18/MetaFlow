import re
import json
from itertools import chain


class SalesforceContextSelector:
    """
    Selects Salesforce metadata relevant to a user requirement.

    The first version uses deterministic whole-word keyword matching.
    This keeps retrieval predictable and easy to test.
    """

    def __init__(self, max_objects: int = 10):
        self.max_objects = max_objects

    def _extract_terms(
        self,
        requirement: str,
    ) -> set[str]:
        """
        Extract normalized terms from the requirement.
        """

        words = re.findall(
            r"[A-Za-z][A-Za-z0-9_]*",
            requirement.lower(),
        )

        return set(words) - {
            "a", "an", "the", "on", "of", "to", "and", "with", "in", "for",
            "create", "add", "update", "delete", "field", "fields", "object",
            "objects", "record", "records", "named", "called", "need", "please",
        }

    def _contains_term(
        self,
        text: str,
        term: str,
    ) -> bool:
        """
        Check whether a term exists as a complete word.

        Example:
            "a" matches "a Contact"
            "a" does NOT match "Account"
        """

        words = re.findall(
            r"[A-Za-z][A-Za-z0-9_]*",
            text.lower(),
        )

        return term.lower() in words

    def select(
        self,
        requirement: str,
        metadata: dict,
    ) -> dict:
        """
        Select relevant Salesforce objects from metadata.
        """

        terms = self._extract_terms(
            requirement
        )

        objects = metadata.get(
            "objects",
            [],
        )

        # Explicit API names/complete labels outrank incidental field matches.
        def phrase(value):
            return " ".join(re.findall(r"[a-z0-9]+", str(value).lower()))

        request_phrase = " " + phrase(requirement) + " "
        explicit = [obj for obj in objects if any(
            normalized and " " + normalized + " " in request_phrase
            for normalized in (phrase(obj.get(key, "")) for key in ("name", "label"))
        )]
        scored_objects = []
        for obj in (explicit if explicit else objects):
            score = 10000 if explicit else 0
            # Each text is tokenized once; preserve separate name/label scores.
            for entry in chain((obj,), obj.get("fields", [])):
                for key in ("name", "label"):
                    tokens = set(re.findall(
                        r"[A-Za-z][A-Za-z0-9_]*", str(entry.get(key, "")).lower()
                    ))
                    score += len(terms & tokens)
            if score > 0:
                scored_objects.append((score, obj))

        # ---------------------------------------------
        # Sort by relevance
        # ---------------------------------------------

        scored_objects.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        # ---------------------------------------------
        # Apply maximum object limit
        # ---------------------------------------------

        selected_objects = [
            obj
            for _, obj in scored_objects[
                : self.max_objects
            ]
        ]

        selected_context = {
            "objects": selected_objects,
            **({"orgTimeZone":metadata["orgTimeZone"]} if "orgTimeZone" in metadata else {}),
            **({"flowDependencies":metadata["flowDependencies"]} if "flowDependencies" in metadata else {})
        }
        return compact_planning_context(requirement, selected_context) if selected_objects else selected_context

# Prompt projection only. Never use this reduced view for validation/preflight.
def compact_planning_context(requirement: str, metadata: dict) -> dict:
    """Keep a complete field inventory, expanding relevant/required dependencies.

    Omitted picklist/formula details are explicitly marked, never presented as
    empty metadata. Full original metadata stays available to backend validators.
    """
    def words(value):
        value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value))
        return set(re.findall(r"[a-z0-9]+", value.lower())) - {
            "c", "r", "field", "fields", "object", "record", "create", "flow",
            "screen", "a", "an", "the", "on", "of", "to", "and", "with",
            "required", "input", "when", "user", "clicks", "finish", "draft",
        }

    # Generation may receive raw discovery metadata rather than selector output.
    # Explicit object names define scope on this path as well.
    def phrase(value):
        return " ".join(re.findall(r"[a-z0-9]+", str(value).lower()))

    request_phrase = " " + phrase(requirement) + " "
    explicit_objects = [obj for obj in metadata.get("objects", []) if any(
        phrase(obj.get(key, "")) and
        " " + phrase(obj.get(key, "")) + " " in request_phrase
        for key in ("name", "label")
    )]
    if explicit_objects:
        metadata = dict(metadata, objects=explicit_objects)

    terms = words(requirement)
    # Action catalogs are irrelevant to ordinary Apex/LWC generation. Keep the
    # full discovery context outside this projection for backend validation.
    action_request = re.search(
        r"\bapex\s+(?:invocable\s+)?action\b|\binvocable\s+apex\b"
        r"|\bsubflow\b|\bemail\s+alert\b|\b(send|sending)\s+(an?\s+)?email\b"
        r"|\bcall\b.*\bflow\b", requirement, re.I,
    )
    result = {k: v for k, v in metadata.items()
              if k in {"orgTimeZone", "validationRuleDiscovery", "focusedObjectRequest", "discoveryScope", "permissionSetCapabilities", "flowDependencies", "namedCredentials"} and (k != "flowDependencies" or action_request)}
    if isinstance(result.get('validationRuleDiscovery'),dict):
        result['validationRuleDiscovery'] = {k: result['validationRuleDiscovery'][k] for k in ('status','objects','activeRuleCount','reason') if k in result['validationRuleDiscovery']}
    result["objects"] = []
    for obj in metadata.get("objects", []):
        fields = obj.get("fields", [])
        by_name = {f.get("name"): f for f in fields if f.get("name")}
        selected = {
            f.get("name") for f in fields
            if f.get("name") in {"Id", "Name", "RecordTypeId"}
            or f.get("nameField")
            or ((f.get("required") or f.get("nillable") is False)
                and f.get("createable") is not False and not f.get("defaultedOnCreate"))
            or terms & (words(f.get("name", "")) | words(f.get("label", "")))
        }
        # Formula and dependent-picklist dependencies must retain full details.
        pending = list(selected)
        while pending:
            f = by_name.get(pending.pop(), {})
            expression = str(f.get("calculatedFormula") or "")
            dependencies = set(re.findall(r"[A-Za-z][A-Za-z0-9_]*", expression))
            dependencies.add(f.get("controllerName"))
            for name in dependencies & by_name.keys():
                if name not in selected:
                    selected.add(name)
                    pending.append(name)
        projected = []
        for field in fields:
            if field.get("name") in selected:
                projected.append({k: field[k] for k in (
                    'name','label','type','required','nillable','createable','updateable',
                    'calculated','calculatedFormula','autoNumber','nameField','length',
                    'precision','scale','referenceTo','relationshipName','defaultedOnCreate',
                    'defaultValue','defaultValueFormula','controllerName','dependentPicklist',
                    'picklistValues','values','restrictedPicklist','unique','externalId'
                ) if k in field})
            else:
                summary = {k: field[k] for k in (
                    "name", "label", "type", "required", "createable", "updateable",
                    "calculated", "autoNumber", "referenceTo", "relationshipName",
                    "defaultedOnCreate", "nillable",
                ) if k in field}
                if summary != field:
                    summary["detailsOmitted"] = True
                projected.append(summary)
        compact = {k: v for k, v in obj.items() if k in {"name", "label", "labelPlural", "createable", "updateable", "deletable", "queryable", "validationRules", "recordTypes"}}
        compact["fields"] = projected
        # Relationship identity remains on each field; retain unusual standalone entries.
        if obj.get("relationships"):
            compact["relationships"] = [{k: r[k] for k in ("name", "relationshipName", "childSObject", "field") if k in r} for r in obj["relationships"] if isinstance(r, dict)]
        if compact.get('validationRules'):
            compact['validationRules'] = [{k: rule[k] for k in ('fullName','name','active','errorConditionFormula','errorMessage','errorDisplayField') if k in rule} for rule in compact['validationRules']]
        result["objects"].append(compact)
    result["contextPolicy"] = (
        "Every selected object's field name/type inventory is included. Fields marked "
        "detailsOmitted have abbreviated metadata, not empty picklists or absent formulas. "
        "Do not invent omitted values or formulas. Report missing configuration if needed."
    )
    # A large org should not make an otherwise actionable request fail before
    # generation.  Escalate from full inventories to a focused projection;
    # never confuse omitted metadata with a missing field or an empty value.
    # The caller retains the original discovery data for semantic validation.
    MAX_CONTEXT_CHARS = 180000  # margin below the provider's overall input budget

    def size():
        return len(json.dumps(result, ensure_ascii=True, separators=(',', ':')))

    if size() > MAX_CONTEXT_CHARS:
        for obj in result['objects']:
            # Keep detailed fields. Replace nonselected fields with a compact
            # inventory so large unrelated picklists cannot exhaust the prompt.
            fields = obj.get('fields', [])
            summaries = [f for f in fields if f.get('detailsOmitted')]
            if summaries:
                obj['fields'] = [f for f in fields if not f.get('detailsOmitted')]
                obj['omittedFieldNames'] = [f['name'] for f in summaries if f.get('name')]
                obj['omittedFieldDetailsCount'] = len(summaries)
        result['contextPolicy'] += (
            ' omittedFieldNames lists fields whose details are not supplied. '
            'Never assume absent field details or enum values. Fetch them from '
            'the authoritative Salesforce context before using them.'
        )

    if size() > MAX_CONTEXT_CHARS:
        # Even the inventory may exceed the budget in exceptional orgs.
        # Keep the counts, not an arbitrarily incomplete prefix of names.
        for obj in result['objects']:
            if obj.pop('omittedFieldNames', None) is not None:
                obj['fieldInventoryOmitted'] = True
        result['contextPolicy'] += (
            ' fieldInventoryOmitted means other fields exist but their names '
            'are not provided here; absence from this projection is NOT proof '
            'that a Salesforce field does not exist.'
        )

    if size() > MAX_CONTEXT_CHARS:
        # Pathological descriptions/formulas on required or directly mentioned
        # fields must not be copied wholesale into an LLM prompt. Mark every
        # excluded value explicitly, preserving identity and type; the full
        # value still exists in the original metadata for authoritative checks.
        detailed_keys = ('calculatedFormula', 'defaultValueFormula', 'defaultValue',
                         'picklistValues', 'values')
        for obj in result['objects']:
            for field in obj.get('fields', []):
                omitted = []
                for key in detailed_keys:
                    if key in field and len(json.dumps(field[key], ensure_ascii=True)) > 8000:
                        del field[key]
                        omitted.append(key)
                if omitted:
                    field['oversizeDetailsOmitted'] = omitted
        result['contextPolicy'] += (
            ' oversizeDetailsOmitted lists specific large values excluded from '
            'the prompt; their content is UNKNOWN to generation, not empty. '
            'Do not generate dependent formulas/picklists until retrieved.'
        )

    if size() > MAX_CONTEXT_CHARS:
        raise ValueError(
            'Required Salesforce metadata remains too large after conservative '
            'projection. Generation was stopped rather than losing needed '
            'schema facts. Divide the requirement into validated stages.'
        )
    return result
