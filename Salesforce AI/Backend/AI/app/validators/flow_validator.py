"""Record-triggered Flow contract with before-save and related-record after-save operations."""
import re
from pydantic_core import PydanticCustomError
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

API_NAME = r"^[A-Za-z][A-Za-z0-9_]*$"
Name = Annotated[str, Field(pattern=API_NAME, min_length=1, max_length=80)]
Text = Annotated[str, Field(min_length=1, max_length=255)]
Reference = Annotated[str, Field(pattern=r"^(?:\$Record|[A-Za-z][A-Za-z0-9_]*)(?:\.[A-Za-z][A-Za-z0-9_]*)?$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


def _checked_flow_edges(config):
    """Validate every connector slot and report exact source/target locations.

    Null terminates an ordinary branch. Start/loop-body/scheduled roots are
    required by their models. No connectors are renamed, dropped or repaired.
    """
    names = [node.name for node in config.elements]
    available = set(names)
    issues = []
    def check(target, path, source):
        if target is not None and target not in available:
            issues.append(dict(code='UNKNOWN_ELEMENT', path=path, source=source,
                               target=target, availableElements=names))
    check(config.startElement, 'startElement', 'Start')
    graph = {}
    for index, node in enumerate(config.elements):
        prefix = f'elements[{index}]'
        edges = []
        if isinstance(node, FlowDecision):
            slots = [('defaultNext', node.defaultNext)]
            slots += [(f'rules[{ri}].next', rule.next) for ri, rule in enumerate(node.rules)]
        else:
            slots = [('next', node.next)]
            if hasattr(node, 'faultNext'):
                slots.append(('faultNext', node.faultNext))
            if hasattr(node, 'nextValue'):
                slots.append(('nextValue', node.nextValue))
        for slot, target in slots:
            check(target, prefix + '.' + slot, node.name)
            if target is not None:
                edges.append(target)
        graph[node.name] = edges
    for index, path in enumerate(getattr(config, 'scheduledPaths', [])):
        check(path.next, f'scheduledPaths[{index}].next', path.name)
    if issues:
        details = '; '.join(
            f"{i['path']} (source {i['source']!r}) targets missing element {i['target']!r}"
            for i in issues
        ) + '. Available elements: ' + ', '.join(names)
        raise PydanticCustomError('flow_graph_reference',
            'Dangling Flow connector or unknown start: {details}',
            {'details': details, 'issues': issues})
    return graph


class FlowValue(StrictModel):
    type: Literal["String", "Number", "Boolean", "Date", "DateTime"]
    value: StrictStr | StrictInt | StrictFloat | StrictBool

    @model_validator(mode="after")
    def check_value(self):
        valid = ((self.type == "String" and type(self.value) is str)
                 or (self.type == "Boolean" and type(self.value) is bool)
                 or (self.type == "Number" and type(self.value) in (int, float)))
        if self.type in {'Date','DateTime'} and type(self.value) is str:
            try:
                if self.type == 'Date':
                    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', self.value): raise ValueError()
                    date.fromisoformat(self.value)
                else:
                    parsed = datetime.fromisoformat(self.value.replace('Z', '+00:00'))
                    if 'T' not in self.value or parsed.tzinfo is None: raise ValueError()
                valid = True
            except ValueError:
                raise ValueError('Date literals require YYYY-MM-DD; DateTime requires ISO 8601 with a time zone.')
        if not valid:
            raise ValueError("Flow value.type must match the literal JSON value type.")
        if isinstance(self.value, str) and any(ord(c) < 32 and c not in '\t\n\r' for c in self.value):
            raise ValueError("Flow strings cannot contain XML control characters.")
        return self


class FlowRecordReference(StrictModel):
    type: Literal["Reference"]
    value: Reference


RecordValue = Annotated[FlowValue | FlowRecordReference, Field(discriminator="type")]


class FlowCondition(StrictModel):
    field: Reference
    operator: Literal["IsNull", "EqualTo", "NotEqualTo", "GreaterThan", "GreaterThanOrEqualTo", "LessThan", "LessThanOrEqualTo", "Contains", "StartsWith", "EndsWith"]
    value: RecordValue

    @model_validator(mode="after")
    def check_operator(self):
        if self.operator == "IsNull" and self.value.type != "Boolean":
            raise ValueError("IsNull requires a Boolean literal.")
        if self.operator in {"GreaterThan", "GreaterThanOrEqualTo", "LessThan", "LessThanOrEqualTo"} and self.value.type not in {"Number", "Date", "DateTime", "Reference"}:
            raise ValueError("Ordered comparison currently requires a Number literal.")
        return self


class FlowRule(StrictModel):
    name: Name
    label: Text
    conditionLogic: Literal["and", "or"]
    conditions: list[FlowCondition] = Field(min_length=1, max_length=20)
    next: Name | None


class FlowDecision(StrictModel):
    kind: Literal["Decision"]
    name: Name
    label: Text
    rules: list[FlowRule] = Field(min_length=1, max_length=20)
    defaultLabel: Text
    defaultNext: Name | None


class FlowAssignmentItem(StrictModel):
    field: Reference
    value: RecordValue

    @model_validator(mode="after")
    def writable_field(self):
        if self.field.startswith('$Record.') and self.field.split('.', 1)[1] in {"Id", "CreatedDate", "CreatedById", "LastModifiedDate", "LastModifiedById", "SystemModstamp", "IsDeleted"}:
            raise ValueError("Assignment targets a system-managed field.")
        return self


class FlowAssignment(StrictModel):
    kind: Literal["Assignment"]
    name: Name
    label: Text
    assignments: list[FlowAssignmentItem] = Field(min_length=1, max_length=50)
    next: Name | None

    @model_validator(mode="after")
    def unique_targets(self):
        names = [a.field for a in self.assignments]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate field assignment in one Assignment node.")
        return self


class FlowInputAssignment(StrictModel):
    field: Name
    value: RecordValue

    @model_validator(mode="after")
    def reject_system_fields(self):
        if self.field in {"Id", "CreatedDate", "CreatedById", "LastModifiedDate", "LastModifiedById", "SystemModstamp", "IsDeleted"}:
            raise ValueError("Record operation cannot assign a system-managed field.")
        return self


class FlowRecordFilter(StrictModel):
    field: Name
    operator: Literal["EqualTo", "NotEqualTo", "GreaterThan", "GreaterThanOrEqualTo", "LessThan", "LessThanOrEqualTo", "IsNull"]
    value: FlowValue

    @model_validator(mode="after")
    def check_filter(self):
        FlowCondition(field="$Record." + self.field, operator=self.operator, value=self.value)
        return self


class FlowCreateRecords(StrictModel):
    kind: Literal["CreateRecords"]
    name: Name
    label: Text
    object: Name
    inputAssignments: list[FlowInputAssignment] = Field(min_length=1, max_length=50)
    next: Name | None
    faultNext: Name | None = None

    @model_validator(mode="after")
    def unique_fields(self):
        names = [a.field for a in self.inputAssignments]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate record input assignment.")
        return self


class FlowUpdateRecords(FlowCreateRecords):
    kind: Literal["UpdateRecords"]
    relationshipField: Name
    filters: list[FlowRecordFilter] = Field(default_factory=list, max_length=20)


FlowNode = Annotated[FlowDecision | FlowAssignment | FlowCreateRecords | FlowUpdateRecords, Field(discriminator="kind")]



class FlowVariable(StrictModel):
    name: Name
    dataType: Literal["String", "Number", "Boolean"]
    value: FlowValue
    scale: int = Field(default=0, ge=0, le=17, strict=True)

    @model_validator(mode="after")
    def matching_default(self):
        if self.value.type != self.dataType:
            raise ValueError("Variable default must match its dataType.")
        if self.dataType != "Number" and self.scale != 0:
            raise ValueError("Only Number variables have a scale.")
        return self


class FlowFormula(StrictModel):
    name: Name
    sourceField: Name
    dataType: Literal["String", "Number", "Boolean", "Date", "DateTime"]
    expression: str = Field(min_length=1, max_length=3900)
    scale: int = Field(default=0, ge=0, le=17, strict=True)
    sourceFingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class FlowConfig(StrictModel):
    flowType: Literal["RecordTriggered"]
    triggerType: Literal["RecordBeforeSave", "RecordAfterSave"]
    recordTriggerType: Literal["Create", "Update", "CreateAndUpdate"]
    object: Name
    status: Literal["Draft"]
    startElement: Name
    elements: list[FlowNode] = Field(min_length=1, max_length=50)
    variables: list[FlowVariable] = Field(default_factory=list, max_length=50)
    formulas: list[FlowFormula] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_graph(self):
        names = [n.name for n in self.elements]
        rule_names = [r.name for n in self.elements if isinstance(n, FlowDecision) for r in n.rules]
        all_names = names + rule_names + [r.name for r in [*self.variables, *self.formulas]]
        if any("__" in name or name.endswith("_") for name in all_names):
            raise ValueError("Flow node/rule names cannot contain double or trailing underscores.")
        if len(all_names) != len(set(all_names)):
            raise ValueError("Flow node and rule names must be unique.")
        graph = _checked_flow_edges(self)
        visiting, visited = set(), set()
        def visit(name):
            if name in visiting:
                raise ValueError(f"Flow cycles/loops are not supported in v1; cycle reaches {name!r}.")
            if name in visited:
                return
            visiting.add(name)
            for target in graph[name]: visit(target)
            visiting.remove(name)
            visited.add(name)
        visit(self.startElement)
        if visited != set(names):
            raise ValueError("Flow contains unreachable nodes: " + ", ".join(sorted(set(names) - visited)))
        if self.triggerType == "RecordBeforeSave":
            if any(isinstance(n, FlowCreateRecords) for n in self.elements):
                raise ValueError("Before-save Flow cannot create/update related records.")
            if not any(isinstance(n, FlowAssignment) for n in self.elements):
                raise ValueError("Before-save Flow must contain an Assignment.")
        else:
            if any(isinstance(n, FlowAssignment) and any(a.field.startswith("$Record.") for a in n.assignments) for n in self.elements):
                raise ValueError("After-save assignments to $Record do not persist; use guarded UpdateRecords after save or an appropriate before-save Assignment.")
            operations = [n for n in self.elements if isinstance(n, FlowCreateRecords)]
            if not operations:
                raise ValueError("After-save Flow must contain CreateRecords or UpdateRecords.")
            self_updates = [n for n in operations if n.object == self.object]
            if self_updates:
                if len(operations) != 1 or not isinstance(self_updates[0], FlowUpdateRecords):
                    raise ValueError("A triggering-record update must be the only record operation; same-object creation and mixed writes are unsupported.")
                node = self_updates[0]
                if node.relationshipField != 'Id':
                    raise ValueError("Triggering-record UpdateRecords must use relationshipField Id.")
                if len(node.inputAssignments) > 20:
                    raise ValueError("Triggering-record updates support at most 20 fields.")
                for assignment in node.inputAssignments:
                    if isinstance(assignment.value, FlowRecordReference):
                        raise ValueError("Triggering-record updates require stable literal values, not references.")
                    if assignment.value.type == 'String' and (not assignment.value.value or assignment.value.value != assignment.value.value.strip()):
                        raise ValueError("Triggering-record String values must be nonempty with no surrounding whitespace.")
        validate_resource_references(self)
        return self


def is_extended_config(config):
    return isinstance(config, dict) and (config.get('contractVersion')==2 or config.get('flowType') in {'Screen','Autolaunched','Scheduled','PlatformEvent'} or config.get('triggerType')=='RecordBeforeDelete')


def flow_config_json_schema():
    from pydantic import TypeAdapter
    return TypeAdapter(FlowConfig | ExtendedFlowConfig).json_schema()


def validate_flow(full_name, label, config):
    if not isinstance(full_name, str) or not re.fullmatch(API_NAME, full_name) or len(full_name) > 80 or '__' in full_name or full_name.endswith('_'):
        raise ValueError("Flow fullName must be an unnamespaced API name (letters, digits, single underscores; no trailing underscore), max 80 characters.")
    if not isinstance(label, str) or not label.strip() or len(label) > 255:
        raise ValueError("Flow requires a non-empty label of at most 255 characters.")
    if is_extended_config(config):
        return ExtendedFlowConfig.model_validate(config)
    return FlowConfig.model_validate(config)


def scalar_type(field):
    return {'string':'String','text':'String','textarea':'String','longtextarea':'String',
            'email':'String','phone':'String','url':'String','picklist':'String','combobox':'String',
            'int':'Number','integer':'Number','double':'Number','number':'Number',
            'currency':'Number','percent':'Number','boolean':'Boolean','checkbox':'Boolean',
            'date':'Date','datetime':'DateTime'}.get(str(field.get('type', '')).lower())


def resource_map(config):
    return {r.name:r for r in [*getattr(config, 'variables', []), *getattr(config, 'formulas', [])]}


def validate_resource_references(config):
    resources = resource_map(config)
    for node in config.elements:
        if isinstance(node, FlowDecision):
            pairs = [(c.field, c.value, False, c.operator) for r in node.rules for c in r.conditions]
        elif isinstance(node, FlowAssignment):
            pairs = [(a.field, a.value, True, None) for a in node.assignments]
        else:
            pairs = [("$Record." + a.field, a.value, False, None) for a in node.inputAssignments]
        for reference, value, assigning, operator in pairs:
            if not reference.startswith('$Record.'):
                target = resources.get(reference)
                if target is None:
                    raise ValueError(f"Unknown Flow resource: {reference}.")
                if assigning and not isinstance(target, FlowVariable):
                    raise ValueError("Formula resources are read-only.")
                value_type = value.type
                if isinstance(value, FlowRecordReference):
                    value_type = resources[value.value].dataType if value.value in resources else None
                if value_type and operator != 'IsNull' and value_type != target.dataType:
                    raise ValueError("Flow resource types do not match.")
                if operator in {'GreaterThan','GreaterThanOrEqualTo','LessThan','LessThanOrEqualTo'} and target.dataType != 'Number':
                    raise ValueError("Ordered resource comparison requires Number.")
            if isinstance(value, FlowRecordReference) and not value.value.startswith('$Record.') and value.value not in resources:
                raise ValueError(f"Unknown Flow resource: {value.value}.")


def validate_flow_fields(config, fields, check_write=False):
    """Validate fields and resources, including current org formula provenance."""
    from Backend.AI.app.services.flow_formula_service import compile_field_formula, check_field_available
    by_name = {f.get('name'): f for f in fields}
    resources = resource_map(config)
    for resource in getattr(config, 'formulas', []):
        expected = compile_field_formula(resource.sourceField, fields, config)
        actual = resource.model_dump(exclude={'name'})
        if expected != actual:
            raise ValueError(f"Formula metadata changed or resource was altered: {resource.sourceField}. Regenerate and reapprove the plan.")

    def resolve(reference, assigning=False):
        if not reference.startswith('$Record.'):
            r = resources.get(reference)
            if r is None: raise ValueError(f"Unknown Flow resource: {reference}.")
            if assigning and not isinstance(r, FlowVariable): raise ValueError("Formula resources are read-only.")
            return r.dataType, None
        name = reference.split('.', 1)[1]
        field = by_name.get(name)
        if field is None: raise ValueError(f"Flow references unknown field {config.object}.{name}.")
        if not assigning:
            check_field_available(name, field, config)
            if getattr(config, 'triggerType', None) == 'RecordBeforeSave' and field.get('calculated'):
                raise ValueError(f"Before-save calculated field {name} must use a resolved Flow formula resource.")
        return scalar_type(field), field

    for node in config.elements:
        if isinstance(node, FlowCreateRecords): continue
        pairs = [(a.field,a.value,True,None) for a in node.assignments] if isinstance(node,FlowAssignment) else [
            (c.field,c.value,False,c.operator) for r in node.rules for c in r.conditions]
        for reference, value, assigning, operator in pairs:
            target_type, field = resolve(reference, assigning)
            value_type = resolve(value.value)[0] if isinstance(value,FlowRecordReference) else value.type
            if operator != 'IsNull' and (target_type is None or target_type != value_type):
                raise ValueError(f"Flow literal type or reference type does not match {config.object}.{reference}.")
            if operator in {'GreaterThan','GreaterThanOrEqualTo','LessThan','LessThanOrEqualTo'} and target_type != 'Number':
                raise ValueError("Ordered comparison requires Number.")
            if assigning and field:
                name=field['name']
                if field.get('calculated') or field.get('autoNumber'):
                    raise ValueError(f"Flow cannot assign calculated/auto-number field {name}.")
                if check_write:
                    flags=['createable'] if config.recordTriggerType=='Create' else ['updateable'] if config.recordTriggerType=='Update' else ['createable','updateable']
                    if any(field.get(flag) is not True for flag in flags):
                        raise ValueError(f"Flow assignment field is not writable for the connected user: {name}.")
                if value.type=='String' and field.get('length') and len(value.value)>field['length']:
                    raise ValueError(f"Flow literal exceeds the field length: {name}.")
                if field.get('restrictedPicklist') and value.type=='String':
                    allowed={p.get('value') for p in field.get('picklistValues',[]) if p.get('active',True)}
                    if value.value not in allowed: raise ValueError(f"Flow literal is not an active picklist value: {name}.")


def validate_flow_context(plan, context):
    from Backend.AI.app.services.planned_context import context_with_planned_components
    context = context_with_planned_components(plan.model_dump(), context)
    objects = {o.get('name'): o for o in context.get('objects', [])}
    for item in plan.items:
        if item.action == 'CREATE' and item.metadataType == 'Flow':
            config = validate_flow(item.fullName, item.label, item.config)
            if isinstance(config, ExtendedFlowConfig):
                validate_extended_context(config, objects, org_timezone=context.get('orgTimeZone'))
                continue
            if config.object not in objects:
                raise ValueError(f"Flow v1 requires an existing object in Salesforce context: {config.object}.")
            validate_flow_fields(config, objects[config.object].get('fields', []))
            validate_record_operations(config, objects)


def validate_flow_spec_matches_plan(plan, specification):
    expected = {i.id:i for i in plan.items if i.metadataType == 'Flow' and i.action == 'CREATE'}
    actual = [i for i in specification.metadata if i.metadataType == 'Flow']
    if len(actual) != len(expected) or {i.itemId for i in actual} != set(expected):
        raise ValueError('Flow metadata items do not match the approved plan.')
    for item in actual:
        approved = expected[item.itemId]
        a = validate_flow(approved.fullName, approved.label, approved.config).model_dump()
        b = validate_flow(item.fullName, item.label, item.config).model_dump()
        if (item.fullName, item.label, item.description, item.dependencies, b) != (approved.fullName, approved.label, approved.description, approved.dependencies, a):
            raise ValueError('Flow metadata changed the approved plan; regenerate metadata without changing its configuration.')


def flow_objects(config):
    if isinstance(config, ExtendedFlowConfig):
        return extended_objects(config)
    return {config.object} | {n.object for n in config.elements if isinstance(n, FlowCreateRecords)}


def validate_record_operations(config, objects, check_write=False):
    """Resolve related-object writes and source references against actual metadata."""
    from types import SimpleNamespace as Obj
    source_fields = {f.get('name'): f for f in objects.get(config.object, {}).get('fields', [])}
    families = {
        'string':'String', 'text':'String', 'textarea':'String', 'longtextarea':'String',
        'email':'String', 'phone':'String', 'url':'String', 'picklist':'String',
        'double':'Number', 'int':'Number', 'integer':'Number', 'number':'Number',
        'currency':'Number', 'percent':'Number', 'boolean':'Boolean', 'checkbox':'Boolean',
        'date':'Date', 'datetime':'DateTime', 'time':'Time',
    }
    for node in config.elements:
        if not isinstance(node, FlowCreateRecords):
            continue
        metadata = objects.get(node.object)
        if metadata is None:
            raise ValueError(f'Flow requires existing target object metadata: {node.object}.')
        fields = metadata.get('fields', [])
        by_name = {f.get('name'): f for f in fields}
        update = isinstance(node, FlowUpdateRecords)
        flag = 'updateable' if update else 'createable'
        if check_write and metadata.get(flag) is not True:
            raise ValueError(f'Target object is not {flag} for the connected user: {node.object}.')
        has_link = False
        for assignment in node.inputAssignments:
            target = by_name.get(assignment.field)
            if target is None:
                raise ValueError(f'Unknown target field: {node.object}.{assignment.field}.')
            if target.get('calculated') or target.get('autoNumber') or (check_write and target.get(flag) is not True):
                raise ValueError(f'Target field is not writable: {node.object}.{assignment.field}.')
            value = assignment.value
            if isinstance(value, FlowRecordReference):
                source_name = value.value.split('.', 1)[1] if value.value.startswith('$Record.') else value.value
                resource = resource_map(config).get(value.value)
                source = {'type': {'String':'string','Number':'double','Boolean':'boolean','Date':'date','DateTime':'datetime'}[resource.dataType]} if resource else source_fields.get(source_name)
                if source is None:
                    raise ValueError(f'Unknown source field reference: {value.value}.')
                source_type = str(source.get('type', '')).lower()
                target_type = str(target.get('type', '')).lower()
                if target_type in {'reference', 'lookup', 'masterdetail'}:
                    refs = {config.object} if source_name == 'Id' else set(source.get('referenceTo') or [])
                    allowed = set(target.get('referenceTo') or [])
                    if source_type not in {'id', 'reference', 'lookup', 'masterdetail'} or not refs or not refs.issubset(allowed):
                        raise ValueError(f'Incompatible lookup reference for {node.object}.{assignment.field}.')
                    if value.value == '$Record.Id': has_link = True
                elif families.get(source_type) is None or families.get(source_type) != families.get(target_type):
                    raise ValueError(f'Incompatible field reference for {node.object}.{assignment.field}.')
            else:
                fake = Obj(object=node.object, recordTriggerType='Update' if update else 'Create', elements=[
                    FlowAssignment(kind='Assignment', name='Check', label='Check', next=None,
                        assignments=[FlowAssignmentItem(field='$Record.' + assignment.field, value=value)])])
                validate_flow_fields(fake, fields, check_write)
        if update:
            relationship = by_name.get(node.relationshipField)
            if node.object == config.object:
                if node.relationshipField != 'Id' or not relationship or str(relationship.get('type','')).lower() != 'id':
                    raise ValueError('Triggering-record UpdateRecords requires the actual Id field.')
                from decimal import Decimal, InvalidOperation
                for assignment in node.inputAssignments:
                    target = by_name[assignment.field]
                    if target.get('filterable') is False or (check_write and target.get('filterable') is not True):
                        raise ValueError(f'Triggering-record update field must be filterable for the unchanged-value guard: {assignment.field}.')
                    if assignment.value.type == 'Number':
                        scale = target.get('scale')
                        if type(scale) is not int or not 0 <= scale <= 17:
                            raise ValueError('Triggering-record numeric updates require verified field scale.')
                        try:
                            number = Decimal(str(assignment.value.value))
                            if number != number.quantize(Decimal(1).scaleb(-scale)):
                                raise ValueError('Triggering-record literal would be rounded by Salesforce; specify a representable value.')
                        except InvalidOperation as exc:
                            raise ValueError('Triggering-record numeric literal exceeds supported precision.') from exc
            elif not relationship or str(relationship.get('type', '')).lower() not in {'reference','lookup','masterdetail'} or config.object not in (relationship.get('referenceTo') or []):
                raise ValueError(f'UpdateRecords relationshipField must reference {config.object}.')
            if check_write and relationship.get('filterable') is not True:
                raise ValueError('UpdateRecords relationshipField is not filterable.')
            for condition in node.filters:
                field = by_name.get(condition.field)
                if not field or (check_write and field.get('filterable') is not True):
                    raise ValueError(f'Unknown or non-filterable update filter: {condition.field}.')
                fake=Obj(object=node.object,elements=[FlowDecision(kind='Decision',name='Check',label='Check',
                    defaultLabel='End',defaultNext=None,rules=[FlowRule(name='Rule',label='Rule',conditionLogic='and',next=None,
                        conditions=[FlowCondition(field='$Record.'+condition.field,operator=condition.operator,value=condition.value)])])])
                validate_flow_fields(fake,fields)
        else:
            if not has_link:
                raise ValueError('CreateRecords must link the created record to $Record.Id through a compatible relationship field.')
            if check_write:
                supplied={a.field for a in node.inputAssignments}
                required={f['name'] for f in fields if f.get('createable') is True and f.get('nillable') is False
                          and f.get('defaultedOnCreate') is False and not f.get('calculated') and not f.get('autoNumber')}
                if required - supplied:
                    raise ValueError('CreateRecords missing required target fields: '+', '.join(sorted(required-supplied)))


# Contracts and validation for additional Flow categories.
def clean_text(value):
    if any(ord(c)<32 and c not in '\t\n\r' for c in value):
        raise ValueError('Flow text contains XML control characters.')
    return value


class ExtendedVariable(StrictModel):
    name: Name
    dataType: Literal['String','Number','Boolean','Date','DateTime','SObject']
    isCollection: bool = False
    isInput: bool = False
    isOutput: bool = False
    value: FlowValue | None = None
    scale: int = Field(default=0, ge=0, le=17, strict=True)
    referenceTo: Name | None = None
    objectType: Name | None = None

    @model_validator(mode='after')
    def types(self):
        if (self.dataType=='SObject') != bool(self.objectType): raise ValueError('SObject variables require objectType; scalar variables cannot have objectType.')
        if self.dataType=='SObject' and self.value is not None: raise ValueError('Record variables cannot use scalar defaults.')
        if self.isCollection and self.value is not None: raise ValueError('Collections start empty; populate them using assignments or record queries.')
        if self.value and self.value.type != self.dataType: raise ValueError('Variable default type mismatch.')
        if self.dataType!='Number' and self.scale: raise ValueError('Scale is only supported for Number.')
        if self.referenceTo and (self.dataType!='String' or self.value is not None):
            raise ValueError('Typed Id variables are String with referenceTo and no hardcoded default.')
        return self


class ScreenVisibility(StrictModel):
    conditionLogic: Literal['and','or'] = 'and'
    conditions: list[FlowCondition] = Field(min_length=1, max_length=20)


class ScreenValidation(StrictModel):
    formulaExpression: str = Field(min_length=1, max_length=3900)
    errorMessage: Text


class FlowChoiceResource(StrictModel):
    name: Name
    choiceText: Text
    dataType: Literal['String','Number','Boolean','Date','DateTime']
    value: FlowValue

    @model_validator(mode='after')
    def typed_value(self):
        if self.value.type != self.dataType: raise ValueError('Choice datatype must match its value.')
        clean_text(self.choiceText)
        return self


class ConstantResource(StrictModel):
    name: Name
    dataType: Literal['String','Number','Boolean','Date','DateTime']
    value: FlowValue
    @model_validator(mode='after')
    def typed_value(self):
        if self.value.type != self.dataType: raise ValueError('Constant datatype must match its value.')
        return self


class ExpressionResource(StrictModel):
    name: Name
    dataType: Literal['String','Number','Boolean','Date','DateTime']
    expression: str = Field(min_length=1,max_length=3900)
    scale: int = Field(default=0,ge=0,le=17,strict=True)
    @model_validator(mode='after')
    def clean(self):
        clean_text(self.expression)
        if self.dataType != 'Number' and self.scale: raise ValueError('Only Number formulas use scale.')
        return self


class TextTemplateResource(StrictModel):
    name: Name
    text: str = Field(min_length=1,max_length=32000)
    isViewedAsPlainText: bool = True
    @property
    def dataType(self): return 'String'


class ScreenInputParameter(StrictModel):
    name: Name
    value: RecordValue


class ScreenOutputParameter(StrictModel):
    name: Name
    variable: Name


class ScreenField(StrictModel):
    name: Name
    fieldType: Literal['InputField','DisplayText','LargeTextArea','PasswordField','DropdownBox','RadioButtons','MultiSelectCheckboxes','MultiSelectPicklist','ComponentInstance']
    fieldText: str = Field(min_length=1,max_length=3000)
    dataType: Literal['String','Number','Boolean','Date','DateTime','Currency'] | None = None
    isRequired: bool = False
    scale: int = Field(default=0,ge=0,le=17,strict=True)
    referenceTo: Name | None = None

    extensionName: str | None = Field(default=None,pattern=r'^[A-Za-z][A-Za-z0-9_]*:[A-Za-z][A-Za-z0-9_]*$')
    inputParameters: list[ScreenInputParameter] = Field(default_factory=list,max_length=50)
    outputParameters: list[ScreenOutputParameter] = Field(default_factory=list,max_length=50)
    choiceReferences: list[Name] = Field(default_factory=list,max_length=200)
    defaultSelectedChoiceReference: Name | None = None
    defaultValue: RecordValue | None = None
    helpText: str | None = Field(default=None,max_length=3000)
    visibilityRule: ScreenVisibility | None = None
    validationRule: ScreenValidation | None = None

    @model_validator(mode='after')
    def types(self):
        clean_text(self.fieldText)
        # Plain text only in this increment; HTML and merge-resource rendering are
        # not silently accepted without their own validation and display contract.
        if any(x in self.fieldText for x in ('<','>','{!')): raise ValueError('Screen text must be plain text without HTML or merge syntax.')
        if self.fieldType=='ComponentInstance':
            if not self.extensionName: raise ValueError('ComponentInstance requires the installed extensionName.')
            if self.dataType or self.defaultValue or self.choiceReferences or self.defaultSelectedChoiceReference or self.referenceTo or self.scale or self.validationRule or self.isRequired: raise ValueError('Component instances use their declared input/output parameters for configuration.')
            if len({p.name for p in self.inputParameters})!=len(self.inputParameters) or len({p.name for p in self.outputParameters})!=len(self.outputParameters): raise ValueError('Duplicate component parameter.')
            return self
        if self.extensionName or self.inputParameters or self.outputParameters: raise ValueError('Only component instances accept extension parameters.')
        if self.fieldType=='DisplayText':
            if self.dataType or self.isRequired or self.scale or self.referenceTo or self.defaultValue or self.choiceReferences or self.validationRule: raise ValueError('DisplayText has no input datatype or required setting.')
        elif self.dataType is None: raise ValueError('Screen input requires dataType.')
        if self.scale and self.dataType not in {'Number','Currency'}: raise ValueError('Only Number screen inputs have scale.')
        if self.referenceTo and self.dataType!='String': raise ValueError('Typed Id screen inputs must use String.')
        choice = self.fieldType in {'DropdownBox','RadioButtons','MultiSelectCheckboxes','MultiSelectPicklist'}
        if choice != bool(self.choiceReferences): raise ValueError('Choice screen controls require choiceReferences; other controls cannot use choices.')
        if len(set(self.choiceReferences)) != len(self.choiceReferences): raise ValueError('Duplicate screen choice.')
        if choice and self.dataType != 'String': raise ValueError('Choice controls use String values in this contract.')
        if self.defaultSelectedChoiceReference and self.defaultSelectedChoiceReference not in self.choiceReferences: raise ValueError('Default choice must be among choiceReferences.')
        if choice and self.defaultValue: raise ValueError('Choice controls use defaultSelectedChoiceReference.')
        if self.fieldType in {'LargeTextArea','PasswordField'} and self.dataType != 'String': raise ValueError('Text controls require String datatype.')
        if self.helpText: clean_text(self.helpText)
        if self.defaultValue and self.defaultValue.type != 'Reference':
            expected = 'Number' if self.dataType == 'Currency' else self.dataType
            if self.defaultValue.type != expected: raise ValueError('Screen default type mismatch.')
        return self


class ScreenNode(StrictModel):
    kind: Literal['Screen']
    name: Name
    label: Text
    fields: list[ScreenField] = Field(min_length=1,max_length=30)
    next: Name | None
    allowBack: bool = False
    allowFinish: bool = True
    allowPause: bool = False
    showFooter: bool = True
    showHeader: bool = True
    backButtonLabel: Text | None = None
    nextOrFinishButtonLabel: Text | None = None
    pauseButtonLabel: Text | None = None
    @model_validator(mode='after')
    def navigation(self):
        if not self.showFooter: raise ValueError('Hiding the footer requires a custom navigation component, which must be verified separately.')
        if self.next is None and not self.allowFinish: raise ValueError('A terminal screen must allow Finish.')
        return self


class QueryFilter(StrictModel):
    field: Name
    operator: Literal['EqualTo','NotEqualTo','GreaterThan','GreaterThanOrEqualTo','LessThan','LessThanOrEqualTo','IsNull','Contains','StartsWith','EndsWith']
    value: RecordValue

    @model_validator(mode='after')
    def operators(self):
        if self.operator=='IsNull' and self.value.type!='Boolean': raise ValueError('IsNull requires Boolean literal.')
        return self


class OutputAssignment(StrictModel):
    field: Name
    variable: Name


class GetRecords(StrictModel):
    kind: Literal['GetRecords']
    name: Name
    label: Text
    object: Name
    filters: list[QueryFilter] = Field(min_length=1,max_length=20)
    outputAssignments: list[OutputAssignment] = Field(default_factory=list,max_length=30)
    outputReference: Name | None = None
    getFirstRecordOnly: bool = True
    queriedFields: list[Name] = Field(default_factory=list,max_length=100)
    next: Name | None
    faultNext: Name | None = None

    @model_validator(mode='after')
    def unique(self):
        if bool(self.outputAssignments)==bool(self.outputReference): raise ValueError('Get Records requires either outputAssignments or outputReference.')
        if not self.getFirstRecordOnly and not self.outputReference: raise ValueError('Collection queries require a record collection outputReference.')
        if self.outputReference and not self.queriedFields: raise ValueError('Record queries require explicit queriedFields.')
        if self.outputAssignments and self.queriedFields: raise ValueError('queriedFields applies only to outputReference.')
        names=[x.variable for x in self.outputAssignments]
        if len(names)!=len(set(names)): raise ValueError('Duplicate Get Records output variable.')
        return self


class CreateRecord(StrictModel):
    kind: Literal['CreateRecords']
    name: Name
    label: Text
    object: Name
    inputAssignments: list[FlowInputAssignment] = Field(min_length=1,max_length=50)
    assignRecordIdTo: Name | None = None
    next: Name | None
    faultNext: Name | None = None

    @model_validator(mode='after')
    def unique(self):
        names=[a.field for a in self.inputAssignments]
        if len(names)!=len(set(names)): raise ValueError('Duplicate record input field.')
        return self


class UpdateRecord(StrictModel):
    kind: Literal['UpdateRecordById']
    name: Name
    label: Text
    object: Name
    recordId: FlowRecordReference
    inputAssignments: list[FlowInputAssignment] = Field(min_length=1,max_length=50)
    next: Name | None
    faultNext: Name | None = None

    @model_validator(mode='after')
    def unique(self):
        names=[a.field for a in self.inputAssignments]
        if len(names)!=len(set(names)): raise ValueError('Duplicate record input field.')
        return self


class DeleteRecord(StrictModel):
    kind: Literal['DeleteRecordById']
    name: Name
    label: Text
    object: Name
    recordId: FlowRecordReference
    next: Name | None
    faultNext: Name | None = None


class FlowCollectionAssignment(StrictModel):
    kind: Literal['CollectionAssignment']
    name: Name
    label: Text
    collection: Name
    operator: Literal['Add','RemoveAll']
    value: RecordValue
    next: Name | None


class FlowLoopNode(StrictModel):
    kind: Literal['Loop']
    name: Name
    label: Text
    collection: Name
    currentItem: Name
    iterationOrder: Literal['Asc','Desc'] = 'Asc'
    nextValue: Name
    next: Name | None


class CallInput(StrictModel):
    name: Name
    value: RecordValue


class CallOutput(StrictModel):
    name: Name
    variable: Name


class SubflowNode(StrictModel):
    kind: Literal['Subflow']
    name: Name
    label: Text
    flowName: Name
    inputs: list[CallInput] = Field(default_factory=list,max_length=50)
    outputs: list[CallOutput] = Field(default_factory=list,max_length=50)
    next: Name | None


class ActionNode(StrictModel):
    kind: Literal['Action']
    name: Name
    label: Text
    actionName: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_.]*$',max_length=255)
    actionType: Literal['apex','emailAlert','emailSimple']
    inputs: list[CallInput] = Field(default_factory=list,max_length=50)
    outputs: list[CallOutput] = Field(default_factory=list,max_length=50)
    next: Name | None
    faultNext: Name | None = None


class RecordCollectionOperation(StrictModel):
    kind: Literal['RecordCollection']
    name: Name
    label: Text
    operation: Literal['Create','Update','Delete']
    object: Name
    inputReference: Name
    next: Name | None
    faultNext: Name | None = None


ExtendedNode = Annotated[FlowDecision | FlowAssignment | ScreenNode | GetRecords | CreateRecord | UpdateRecord | DeleteRecord | FlowCollectionAssignment | FlowLoopNode | SubflowNode | ActionNode | RecordCollectionOperation, Field(discriminator='kind')]


class Schedule(StrictModel):
    frequency: Literal['Once','Daily','Weekly']
    startDate: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    startTime: str = Field(pattern=r'^\d{2}:\d{2}:\d{2}$')
    timeZone: str = Field(min_length=1,max_length=80)

    @model_validator(mode='after')
    def valid_time(self):
        self.utc_start()
        return self

    def utc_start(self):
        try:
            local=datetime.combine(date.fromisoformat(self.startDate),time.fromisoformat(self.startTime))
            zone=ZoneInfo(self.timeZone)
        except (ValueError,ZoneInfoNotFoundError) as exc:
            raise ValueError('Schedule requires an actual date, HH:MM:SS time and IANA time zone.') from exc
        first=local.replace(tzinfo=zone,fold=0);second=local.replace(tzinfo=zone,fold=1)
        if first.utcoffset()!=second.utcoffset() or first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)!=local:
            raise ValueError('Schedule start time is ambiguous or nonexistent at a daylight-saving transition.')
        return first.astimezone(timezone.utc)


class ScheduledPath(StrictModel):
    name: Name
    label: Text
    next: Name
    pathType: Literal['AsyncAfterCommit'] | None = None
    timeSource: Literal['RecordTriggerEvent','RecordField'] | None = None
    recordField: Name | None = None
    offsetNumber: int | None = Field(default=None,ge=-999,le=999,strict=True)
    offsetUnit: Literal['Minutes','Hours','Days'] | None = None
    @model_validator(mode='after')
    def timing(self):
        if self.pathType=='AsyncAfterCommit':
            if any(x is not None for x in [self.timeSource,self.recordField,self.offsetNumber,self.offsetUnit]): raise ValueError('Async paths do not have time offsets.')
        else:
            if self.timeSource is None or self.offsetNumber is None or self.offsetUnit is None: raise ValueError('Scheduled paths require timeSource and explicit offset.')
            if (self.timeSource=='RecordField') != bool(self.recordField): raise ValueError('RecordField timeSource requires a Date/DateTime field.')
        return self


class DynamicChoiceSet(StrictModel):
    name: Name
    mode: Literal['Picklist','Records']
    dataType: Literal['String','Picklist','Multipicklist'] = 'String'
    object: Name
    picklistField: Name | None = None
    displayField: Name | None = None
    valueField: Name | None = None
    filters: list[QueryFilter] = Field(default_factory=list,max_length=20)
    limit: int = Field(default=100,ge=1,le=200,strict=True)
    @property
    def metadata_data_type(self):
        # Legacy String denotes a single-select source, not the XML datatype.
        # Live context validation rejects it for multi-select source fields.
        return 'Picklist' if self.mode == 'Picklist' and self.dataType == 'String' else self.dataType

    @model_validator(mode='after')
    def shape(self):
        if self.mode=='Picklist':
            if not self.picklistField or self.displayField or self.valueField or self.filters: raise ValueError('Picklist choices require object and picklistField only.')
        elif self.picklistField or not self.displayField or not self.valueField or not self.filters: raise ValueError('Record choices require displayField, valueField and explicit filters.')
        if self.mode == 'Records' and self.dataType != 'String':
            raise ValueError('Record choice sets require String dataType in this contract.')
        return self


class ExtendedFlowConfig(StrictModel):
    contractVersion: Literal[2] | None = None
    flowType: Literal['Screen','Autolaunched','Scheduled','PlatformEvent','RecordTriggered']
    triggerType: Literal['Scheduled','PlatformEvent','RecordBeforeDelete','RecordBeforeSave','RecordAfterSave'] | None = None
    recordTriggerType: Literal['Delete','Create','Update','CreateAndUpdate'] | None = None
    object: Name | None = None
    status: Literal['Draft']
    startElement: Name
    elements: list[ExtendedNode] = Field(min_length=1,max_length=50)
    variables: list[ExtendedVariable] = Field(default_factory=list,max_length=50)
    formulas: list[FlowFormula] = Field(default_factory=list,max_length=50)
    constants: list[ConstantResource] = Field(default_factory=list,max_length=50)
    expressions: list[ExpressionResource] = Field(default_factory=list,max_length=50)
    textTemplates: list[TextTemplateResource] = Field(default_factory=list,max_length=50)
    dynamicChoices: list[DynamicChoiceSet] = Field(default_factory=list,max_length=50)
    choices: list[FlowChoiceResource] = Field(default_factory=list,max_length=200)
    scheduledPaths: list[ScheduledPath] = Field(default_factory=list,max_length=10)
    doesRequireRecordChangedToMeetCriteria: bool = False
    schedule: Schedule | None = None
    startFilters: list[FlowRecordFilter] = Field(default_factory=list,max_length=20)

    @model_validator(mode='after')
    def graph(self):
        expected={'Screen':None,'Autolaunched':None,'Scheduled':'Scheduled','PlatformEvent':'PlatformEvent','RecordTriggered':'RecordBeforeDelete'}[self.flowType]
        if self.flowType=='RecordTriggered' and self.contractVersion==2 and self.triggerType in {'RecordBeforeSave','RecordAfterSave'}: expected=self.triggerType
        if self.triggerType!=expected: raise ValueError('Flow type and triggerType do not match.')
        if self.flowType in {'Screen','Autolaunched'} and (self.object or self.startFilters): raise ValueError('Untriggered Flows have no triggering object or Start filters.')
        if self.flowType=='RecordTriggered':
            if not self.object: raise ValueError('Record-triggered Flow requires an object.')
            if self.triggerType=='RecordBeforeDelete' and self.recordTriggerType!='Delete': raise ValueError('Deletion Flow requires recordTriggerType Delete.')
            if self.triggerType!='RecordBeforeDelete' and self.recordTriggerType not in {'Create','Update','CreateAndUpdate'}: raise ValueError('Save-triggered Flow requires a create/update event.')
        elif self.recordTriggerType is not None: raise ValueError('recordTriggerType only applies to the deletion contract here.')
        if self.flowType=='PlatformEvent' and (not self.object or not self.object.endswith('__e')):
            raise ValueError('PlatformEvent Flow requires an existing custom platform event API name ending __e.')
        if self.flowType=='Scheduled':
            if self.schedule is None: raise ValueError('Scheduled Flow requires frequency, date, time and timeZone.')
            if self.object and not self.startFilters: raise ValueError('Object-based Scheduled Flow requires explicit Start filters.')
            if not self.object and self.startFilters: raise ValueError('Start filters require a scheduled object.')
        elif self.schedule is not None or (self.startFilters and self.flowType!='RecordTriggered'): raise ValueError('Schedule and Start filters are only supported for Scheduled Flows.')
        if self.scheduledPaths and self.triggerType!='RecordAfterSave': raise ValueError('Scheduled/asynchronous paths require an after-save Flow.')
        if self.doesRequireRecordChangedToMeetCriteria and (not self.startFilters or self.triggerType not in {'RecordBeforeSave','RecordAfterSave'} or self.recordTriggerType=='Create'): raise ValueError('Changed-to-meet-criteria requires update entry filters.')
        if self.scheduledPaths and self.recordTriggerType!='Create' and not self.doesRequireRecordChangedToMeetCriteria: raise ValueError('Update-triggered scheduled paths require changed-to-meet entry criteria.')
        if self.triggerType=='RecordBeforeSave' and any(not isinstance(n,(FlowAssignment,FlowDecision,GetRecords,FlowLoopNode,FlowCollectionAssignment)) for n in self.elements): raise ValueError('Before-save Flows only allow local logic and Get Records.')
        if self.flowType not in {'Screen','Autolaunched'} and any(v.isInput or v.isOutput for v in self.variables):
            raise ValueError('Triggered Flow variables cannot be exposed as inputs or outputs.')
        if self.formulas and not self.object: raise ValueError('Org-derived formulas require a triggering object.')
        screens=[n for n in self.elements if isinstance(n,ScreenNode)]
        if bool(screens)!=(self.flowType=='Screen'): raise ValueError('Screen Flows require a Screen node; other types cannot contain screens.')
        names=[n.name for n in self.elements];all_names=names+[v.name for v in self.variables]+[f.name for f in self.formulas]
        all_names += [p.name for p in self.scheduledPaths]
        all_names += [r.name for r in [*self.constants,*self.expressions,*self.textTemplates,*self.choices,*self.dynamicChoices]]
        all_names += [r.name for n in self.elements if isinstance(n,FlowDecision) for r in n.rules]
        all_names += [f.name for n in screens for f in n.fields]
        locations = {}
        def register(name, location):
            locations.setdefault(name, []).append(location)
        for index, node in enumerate(self.elements):
            register(node.name, f'elements[{index}].name')
            if isinstance(node, FlowDecision):
                for ri, rule in enumerate(node.rules):
                    register(rule.name, f'elements[{index}].rules[{ri}].name')
            if isinstance(node, ScreenNode):
                for fi, field in enumerate(node.fields):
                    register(field.name, f'elements[{index}].fields[{fi}].name')
        for group in ('variables', 'formulas', 'scheduledPaths', 'constants',
                      'expressions', 'textTemplates', 'choices', 'dynamicChoices'):
            for index, resource in enumerate(getattr(self, group)):
                register(resource.name, f'{group}[{index}].name')
        problems = []
        for name, paths in locations.items():
            if len(paths) > 1:
                problems.append(f'Duplicate internal name {name!r} at ' + ', '.join(paths))
            if '__' in name or name.endswith('_'):
                problems.append(f'Invalid internal name {name!r} at ' + ', '.join(paths))
        if problems:
            raise ValueError(
                'Flow element, resource, rule and screen-field names must be unique, '
                'with no double/trailing underscores. ' + '; '.join(problems)
                + '. Screen inputs already define resources; do not redeclare them as variables. '
                'Salesforce object/field API names retain their __c suffixes.'
            )
        graph = _checked_flow_edges(self)
        roots=[self.startElement,*[p.next for p in self.scheduledPaths]]
        visited=set();active=set()
        def visit(name):
            if name in active:
                if isinstance(next(n for n in self.elements if n.name==name),FlowLoopNode): return
                raise ValueError(f'Only explicit Loop back-edges are allowed; cycle reaches {name!r}.')
            if name in visited:return
            active.add(name)
            for target in graph[name]:visit(target)
            active.remove(name);visited.add(name)
        for root in roots: visit(root)
        if visited!=set(names):raise ValueError('Unreachable Flow nodes: ' + ', '.join(sorted(set(names)-visited)))
        variables={v.name for v in self.variables}
        for n in self.elements:
            if isinstance(n,FlowAssignment) and any(a.field.split('.',1)[0] not in variables and not (self.triggerType=='RecordBeforeSave' and a.field.startswith('$Record.')) for a in n.assignments):
                raise ValueError('Extended-flow Assignment targets must be declared variables; use UpdateRecordById for persisted changes.')
            if isinstance(n,(CreateRecord,UpdateRecord)) and n.object.endswith('__e'):
                raise ValueError('Platform event publication is not a supported record-write action.')
            if self.triggerType in {'RecordBeforeDelete','PlatformEvent'} and isinstance(n,(CreateRecord,UpdateRecord)) and n.object==self.object:
                raise ValueError('Cannot write the deleting record object or triggering event object.')
        # Screen outputs are unavailable before the screen has executed on every path.
        predecessors={n:[] for n in names}
        for n,targets in graph.items():
            for target in targets:predecessors[target].append(n)
        dom={n:({n} if n in roots else set(names)) for n in names}
        for _ in names:
            for n in names:
                if n not in roots:
                    dom[n]={n}|set.intersection(*(dom[p] for p in predecessors[n]))
        outputs={f.name:n.name for n in screens for f in n.fields if f.fieldType!='DisplayText'}
        known=variables|set(outputs)|{f.name for f in [*self.formulas,*self.constants,*self.expressions,*self.textTemplates]}
        for n in self.elements:
            for ref in node_reads(n):
                if ref.startswith('$Record.'):
                    if not self.object:raise ValueError('$Record is unavailable in this Flow.')
                elif ref.split('.',1)[0] not in known:raise ValueError(f'Unknown Flow resource: {ref}.')
                elif ref in outputs and (outputs[ref] not in dom[n.name] or outputs[ref]==n.name):
                    raise ValueError(f'Screen field {ref} may be read before its screen executes.')
        # After-save writes to the source object require the entry condition
        # transition gate, so an unchanged qualifying record cannot re-enter.
        if self.triggerType=='RecordAfterSave' and any(isinstance(n,(UpdateRecord,CreateRecord,DeleteRecord)) and n.object==self.object for n in self.elements):
            if any(isinstance(n,(CreateRecord,DeleteRecord)) and n.object==self.object for n in self.elements): raise ValueError('After-save source-object create/delete is unsupported.')
            if self.recordTriggerType!='Create' and not self.doesRequireRecordChangedToMeetCriteria: raise ValueError('After-save source-object writes require changed-to-meet entry conditions.')
        validate_extended_resources(self,dom)
        return self


def node_reads(node):
    refs=[]
    def value(v):
        if isinstance(v,FlowRecordReference):refs.append(v.value)
    if isinstance(node,FlowDecision):
        for r in node.rules:
            for c in r.conditions:refs.append(c.field);value(c.value)
    elif isinstance(node,FlowAssignment):
        for a in node.assignments:value(a.value)
    elif isinstance(node,GetRecords):
        for f in node.filters:value(f.value)
    elif isinstance(node,(CreateRecord,UpdateRecord)):
        for a in node.inputAssignments:value(a.value)
        if isinstance(node,UpdateRecord):value(node.recordId)
    elif isinstance(node,ScreenNode):
        for field in node.fields:
            for parameter in field.inputParameters:value(parameter.value)
    elif isinstance(node,RecordCollectionOperation): refs.append(node.inputReference)
    elif isinstance(node,DeleteRecord): value(node.recordId)
    elif isinstance(node,FlowCollectionAssignment): value(node.value)
    elif isinstance(node,FlowLoopNode): refs.append(node.collection)
    elif isinstance(node,(ActionNode,SubflowNode)):
        for item in node.inputs:value(item.value)
    return refs


def extended_objects(config):
    return ({config.object} if config.object else set()) | {n.object for n in config.elements if isinstance(n,(GetRecords,CreateRecord,UpdateRecord,DeleteRecord,RecordCollectionOperation))} | {v.objectType for v in config.variables if v.objectType} | {c.object for c in config.dynamicChoices}


def validate_extended_context(config,objects,check_write=False,org_timezone=None):
    from Backend.AI.app.services.flow_formula_service import compile_field_formula
    for name in extended_objects(config):
        if name not in objects:raise ValueError(f'Flow requires existing org metadata for {name}.')
    if config.schedule:
        if not org_timezone or config.schedule.timeZone!=org_timezone:
            raise ValueError('Schedule timeZone must match the verified Salesforce org time zone.')
        if check_write and config.schedule.utc_start()<=datetime.now(timezone.utc):
            raise ValueError('Schedule start is in the past; generate and approve a future start before deployment.')
    if config.object and config.flowType=='Scheduled' and check_write and objects[config.object].get('queryable') is not True:
        raise ValueError('Scheduled object is not queryable.')
    variables={v.name:v for v in config.variables}
    screens={f.name:f for n in config.elements if isinstance(n,ScreenNode) for f in n.fields if f.fieldType!='DisplayText'}
    formulas={f.name:f for f in [*config.formulas,*config.constants,*config.expressions,*config.textTemplates]}
    source={f['name']:f for f in objects.get(config.object,{}).get('fields',[])}
    for formula in config.formulas:
        if compile_field_formula(formula.sourceField,list(source.values()),config)!=formula.model_dump(exclude={'name'}):
            raise ValueError('Approved formula source changed; regenerate and reapprove.')

    def field_info(obj,name):
        field=next((f for f in objects[obj].get('fields',[]) if f.get('name')==name),None)
        if field is None:raise ValueError(f'Unknown or inaccessible field {obj}.{name}.')
        typ=str(field.get('type','')).lower()
        refs={obj} if typ=='id' else set(field.get('referenceTo') or []) if typ in {'reference','lookup','masterdetail'} else set()
        return ('Id' if refs else scalar_type(field)),refs,field
    for expression in config.expressions:
        for reference in re.findall(r'\{!([^}]+)\}', expression.expression):
            if reference.startswith('$Record.') and config.object:
                field_info(config.object, reference.split('.', 1)[1])

    def resource(name):
        if name.startswith('$Record.'):
            if not config.object:raise ValueError('$Record is unavailable.')
            typ,refs,field=field_info(config.object,name.split('.',1)[1])
            if config.triggerType=='RecordBeforeSave' and field.get('calculated'): raise ValueError('Before-save formula field reads require a verified formula resource, not a copied variable.')
            return typ,refs
        if '.' in name:
            owner,field_name=name.split('.',1);var=variables.get(owner)
            if not var or var.dataType!='SObject' or var.isCollection: raise ValueError('Field references require a scalar SObject variable.')
            typ,refs,_=field_info(var.objectType,field_name);return typ,refs
        r=variables.get(name) or screens.get(name) or formulas.get(name)
        if not r:raise ValueError(f'Unknown resource {name}.')
        if getattr(r,'dataType',None)=='SObject': return ('SObject[]' if r.isCollection else 'SObject',{r.objectType})
        ref=getattr(r,'referenceTo',None)
        return (('Id[]' if getattr(r,'isCollection',False) else 'Id'),{ref}) if ref else ((('Number' if r.dataType=='Currency' else r.dataType)+('[]' if getattr(r,'isCollection',False) else '')),set())
    def value_type(v):return resource(v.value) if isinstance(v,FlowRecordReference) else (v.type,set())
    def match(target, actual, location='Flow resource'):
        if target[0] is None or target[0] != actual[0] or (
            target[0] in {'Id', 'Id[]', 'SObject', 'SObject[]'}
            and not actual[1].issubset(target[1])
        ):
            def describe(value):
                typ, object_names = value
                if object_names:
                    return f"{typ}<{', '.join(sorted(object_names))}>"
                return str(typ)

            message = (
                'Flow field/resource types or Id object types do not match '
                f'at {location}: expected {describe(target)}, got {describe(actual)}.'
            )
            if target[0] in {'Id', 'Id[]'} or actual[0] in {'Id', 'Id[]'} or target[1] or actual[1]:
                message += (
                    ' A Salesforce record-Id variable must use dataType String '
                    'and referenceTo set to the matching object API name.'
                )
            raise ValueError(message)
    def literal_constraints(field,value):
        if value.type=='String':
            if field.get('length') and len(value.value)>field['length']:raise ValueError('Flow literal exceeds field length.')
            if field.get('restrictedPicklist') and value.value not in {p.get('value') for p in field.get('picklistValues',[]) if p.get('active',True)}:
                raise ValueError('Flow literal is not an active picklist API value.')
    def filter_check(obj,f):
        typ,refs,field=field_info(obj,f.field)
        if field.get('filterable') is False or (check_write and field.get('filterable') is not True):raise ValueError('Flow query/filter field is not filterable.')
        if f.operator!='IsNull':match((typ,refs),value_type(f.value),f'GetRecords filter {obj}.{f.field}')
        if f.operator in {'GreaterThan','GreaterThanOrEqualTo','LessThan','LessThanOrEqualTo'} and typ not in {'Number','Date','DateTime'}:raise ValueError('Ordered comparisons require Number, Date or DateTime operands.')
    for choice in config.dynamicChoices:
        if choice.mode=='Picklist':
            _,_,field=field_info(choice.object,choice.picklistField)
            if str(field.get('type','')).lower() not in {'picklist','multipicklist'}: raise ValueError('Dynamic picklist choices require a picklist field.')
            expected = 'Multipicklist' if str(field.get('type','')).lower() == 'multipicklist' else 'Picklist'
            if choice.metadata_data_type != expected:
                raise ValueError(f'Choice set {choice.name} requires dataType {expected} for {choice.object}.{choice.picklistField}.')
        else:
            if check_write and objects[choice.object].get('queryable') is not True: raise ValueError('Record choices require a queryable object.')
            display,_,_=field_info(choice.object,choice.displayField)
            typ,_,_=field_info(choice.object,choice.valueField)
            if display!='String' or typ not in {'String','Id'}: raise ValueError('Record choices require text display and String/Id value fields.')
            for f in choice.filters:filter_check(choice.object,f)
    for path in config.scheduledPaths:
        if path.recordField:
            typ,_,_=field_info(config.object,path.recordField)
            if typ not in {'Date','DateTime'}: raise ValueError('Scheduled path time source must be Date or DateTime.')
    for f in config.startFilters:filter_check(config.object,f)
    for n in config.elements:
        if isinstance(n,FlowDecision):
            for rule in n.rules:
                for c in rule.conditions:
                    typ,refs=resource(c.field)
                    if c.operator!='IsNull':match((typ,refs),value_type(c.value),f'Decision {n.name} condition {c.field}')
                    if c.operator in {'GreaterThan','GreaterThanOrEqualTo','LessThan','LessThanOrEqualTo'} and typ not in {'Number','Date','DateTime'}:raise ValueError('Ordered Decision comparison requires Number, Date or DateTime.')
        elif isinstance(n,FlowAssignment):
            for a in n.assignments:
                target,actual=resource(a.field),value_type(a.value)
                if '.' in a.field and not a.field.startswith('$Record.'):
                    owner,key=a.field.split('.',1);var=variables.get(owner)
                    if not var or var.dataType!='SObject' or var.isCollection: raise ValueError('Record field assignment requires a scalar record variable.')
                    _,_,field=field_info(var.objectType,key)
                    if key in {'Id','CreatedDate','CreatedById','LastModifiedDate','LastModifiedById','SystemModstamp','IsDeleted'} or field.get('calculated') or field.get('autoNumber') or (check_write and not (field.get('createable') or field.get('updateable'))): raise ValueError('Record variable field is not writable.')
                if a.field.startswith('$Record.'):

                    _,_,field=field_info(config.object,a.field.split('.',1)[1])
                    if config.triggerType!='RecordBeforeSave' or field.get('calculated') or field.get('autoNumber') or (check_write and any(field.get(flag) is not True for flag in (['createable'] if config.recordTriggerType=='Create' else ['updateable'] if config.recordTriggerType=='Update' else ['createable','updateable']))): raise ValueError('Triggering field is not writable before save.')
                # Platform events carry identifiers as Text fields. An explicitly
                # declared typed-Id variable makes the conversion reviewable;
                # Salesforce validates the supplied Id when the record operation runs.
                if not (config.flowType=='PlatformEvent' and target[0]=='Id' and actual[0]=='String' and isinstance(a.value,FlowRecordReference)):
                    match(target,actual,f'Assignment {n.name} field {a.field}')
        elif isinstance(n,RecordCollectionOperation):
            match(('SObject[]',{n.object}),resource(n.inputReference),f'{n.kind} {n.name} inputReference')
            flag={'Create':'createable','Update':'updateable','Delete':'deletable'}[n.operation]
            if check_write and objects[n.object].get(flag) is not True: raise ValueError('Bulk operation object lacks '+flag+' access.')
            if config.triggerType in {'RecordBeforeSave','RecordBeforeDelete','PlatformEvent','RecordAfterSave'} and n.object==config.object: raise ValueError('Bulk writes to the triggering object are not supported.')
        elif isinstance(n,DeleteRecord):
            match(('Id',{n.object}),value_type(n.recordId),f'DeleteRecordById {n.name}.recordId')
            if config.flowType in {'RecordTriggered','PlatformEvent'} and n.object==config.object: raise ValueError('Cannot delete the triggering object through this contract.')
            if check_write and objects[n.object].get('deletable') is not True: raise ValueError('Delete target object is not deletable.')
        elif isinstance(n,FlowCollectionAssignment):
            typ,refs=resource(n.collection)
            if not typ.endswith('[]'): raise ValueError('CollectionAssignment requires a collection variable.')
            match((typ[:-2],refs),value_type(n.value),f'CollectionAssignment {n.name}.value')
        elif isinstance(n,FlowLoopNode):
            typ,refs=resource(n.collection)
            if not typ.endswith('[]'): raise ValueError('Loop requires a collection.')
            match(resource(n.currentItem),(typ[:-2],refs),f'Loop {n.name}.currentItem')
        elif isinstance(n,GetRecords):
            if check_write and objects[n.object].get('queryable') is not True:raise ValueError('Get Records object is not queryable.')
            _,_,idfield=field_info(n.object,'Id')
            if check_write and idfield.get('sortable') is not True:raise ValueError('Get Records requires sortable Id for deterministic first-record selection.')
            for f in n.filters:filter_check(n.object,f)
            if n.outputReference:
                match(('SObject' if n.getFirstRecordOnly else 'SObject[]',{n.object}),resource(n.outputReference),f'GetRecords {n.name}.outputReference')
                for name in n.queriedFields: field_info(n.object,name)
            for out in n.outputAssignments:
                if out.variable not in variables:raise ValueError('Get Records output must target a declared variable.')
                typ,refs,_=field_info(n.object,out.field);match(resource(out.variable),(typ,refs),f'GetRecords {n.name} output {n.object}.{out.field} -> {out.variable}')
        elif isinstance(n,(CreateRecord,UpdateRecord)):
            update=isinstance(n,UpdateRecord);flag='updateable' if update else 'createable'
            if check_write and objects[n.object].get(flag) is not True:raise ValueError(f'Object is not {flag}: {n.object}.')
            if update:
                match(('Id',{n.object}),value_type(n.recordId),f'UpdateRecordById {n.name}.recordId')
                _,_,idfield=field_info(n.object,'Id')
                if check_write and idfield.get('filterable') is not True:raise ValueError('Update target Id must be filterable.')
            elif n.assignRecordIdTo:
                if n.assignRecordIdTo not in variables:raise ValueError('Created Id output requires a declared variable.')
                match(resource(n.assignRecordIdTo),('Id',{n.object}),f'CreateRecords {n.name}.assignRecordIdTo')
            for a in n.inputAssignments:
                typ,refs,field=field_info(n.object,a.field)
                if field.get('calculated') or field.get('autoNumber') or field.get(flag) is False or (check_write and field.get(flag) is not True):raise ValueError(f'Field is not writable: {n.object}.{a.field}.')
                match((typ,refs),value_type(a.value),f'{n.kind} {n.name} assignment {n.object}.{a.field}');literal_constraints(field,a.value)
                if config.triggerType=='RecordBeforeDelete' and typ=='Id' and config.object in refs:
                    raise ValueError('Cannot create/update a lookup pointing to the record being deleted.')
            if not update and check_write:
                required={f['name'] for f in objects[n.object]['fields'] if f.get('createable') is True and f.get('nillable') is False and f.get('defaultedOnCreate') is False and not f.get('calculated') and not f.get('autoNumber')}
                missing=required-{a.field for a in n.inputAssignments}
                if missing:raise ValueError('Missing required create fields: '+', '.join(sorted(missing)))


def validate_extended_resources(config,dominators):
    resources={r.name:r for r in [*config.variables,*config.formulas,*config.constants,*config.expressions,*config.textTemplates]}
    screen_fields={f.name:(n.name,f) for n in config.elements if isinstance(n,ScreenNode) for f in n.fields}
    choices={r.name:r for r in [*config.choices,*config.dynamicChoices]}
    variables={r.name:r for r in config.variables}
    def refs(expression):
        clean_text(expression)
        return re.findall(r'\{!([^}]+)\}',expression)
    def exists(reference):
        if reference.startswith('$Record.') and config.object: return
        if reference in {'$Flow.CurrentDate','$Flow.CurrentDateTime','$Flow.FaultMessage'}: return
        if reference.split('.',1)[0] not in resources and reference not in screen_fields: raise ValueError('Unknown formula/template resource: '+reference)
    for r in [*config.expressions,*config.textTemplates]:
        for reference in refs(getattr(r,'expression',None) or r.text): exists(reference)
    for n in config.elements:
        if isinstance(n,ScreenNode):
            for f in n.fields:
                for parameter in f.outputParameters:
                    if parameter.variable not in variables: raise ValueError('Component outputs must map to declared variables.')
                for name in f.choiceReferences:
                    if name not in choices or choices[name].dataType not in {'String','Picklist','Multipicklist'}: raise ValueError('Screen choice must reference a declared text-compatible choice.')
                    if f.referenceTo:
                        choice=choices[name]
                        if not isinstance(choice,DynamicChoiceSet) or choice.mode!='Records' or choice.valueField!='Id' or choice.object!=f.referenceTo: raise ValueError('Typed Id choices must select Id from the declared target object.')
                if f.defaultValue and f.defaultValue.type=='Reference':
                    exists(f.defaultValue.value)
                    if f.defaultValue.value in screen_fields:
                        owner=screen_fields[f.defaultValue.value][0]
                        if owner==n.name or owner not in dominators[n.name]: raise ValueError('Screen default refers to an input before it is available.')
                for reference in refs(f.validationRule.formulaExpression) if f.validationRule else []: exists(reference)
                for c in f.visibilityRule.conditions if f.visibilityRule else []:
                    exists(c.field)
                    if c.value.type=='Reference': exists(c.value.value)
        if isinstance(n,FlowLoopNode):
            if n.currentItem not in variables or variables[n.currentItem].isCollection: raise ValueError('Loop currentItem requires a scalar variable.')
            if n.collection not in variables or not variables[n.collection].isCollection: raise ValueError('Loop collection must be declared.')
            if n.currentItem==n.collection: raise ValueError('Loop currentItem must differ from collection.')
        if isinstance(n,FlowCollectionAssignment) and (n.collection not in variables or not variables[n.collection].isCollection): raise ValueError('Collection assignment target must be declared.')
        if isinstance(n,(ActionNode,SubflowNode)):
            if len({x.name for x in n.inputs})!=len(n.inputs) or len({x.name for x in n.outputs})!=len(n.outputs): raise ValueError('Duplicate call input/output parameter.')
            if any(x.variable not in variables for x in n.outputs): raise ValueError('Call outputs must target declared variables.')
    output_owners={p.variable:n.name for n in config.elements if isinstance(n,ScreenNode) for f in n.fields for p in f.outputParameters}
    for n in config.elements:
        for reference in node_reads(n):
            if reference in output_owners and (output_owners[reference]==n.name or output_owners[reference] not in dominators[n.name]): raise ValueError('Component output may be read before its screen executes.')
    # Explicit loops can only perform local assignments/decisions; record operations
    # and external calls must occur outside the loop to avoid per-record DML/calls.
    by_name={n.name:n for n in config.elements}
    for loop in [n for n in config.elements if isinstance(n,FlowLoopNode)]:
        seen=set()
        def body(name):
            if name==loop.name:return
            if name is None:raise ValueError('Every loop body path must return to its Loop.')
            if name in seen:return
            seen.add(name);n=by_name[name]
            if isinstance(n,FlowCollectionAssignment) and n.collection==loop.collection: raise ValueError('A loop cannot modify the collection it is iterating.')
            if isinstance(n,FlowAssignment) and any(a.field==loop.collection for a in n.assignments): raise ValueError('A loop cannot replace the collection it is iterating.')
            if not isinstance(n,(FlowAssignment,FlowCollectionAssignment,FlowDecision)): raise ValueError('Loop bodies support local Assignment and Decision nodes only; bulk operations belong after the loop.')
            targets=[n.defaultNext,*[r.next for r in n.rules]] if isinstance(n,FlowDecision) else [n.next]
            for target in targets:body(target)
        body(loop.nextValue)
