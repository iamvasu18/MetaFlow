"""Deterministic Salesforce XML for the validated Flow v1 graph."""
import json
from Backend.AI.app.validators.flow_validator import ExtendedFlowConfig, ScreenNode, GetRecords, CreateRecord, UpdateRecord
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from Backend.AI.app.validators.flow_validator import validate_flow, FlowAssignment, FlowDecision, FlowRecordReference, FlowUpdateRecords, FlowValue

NS = 'http://soap.sforce.com/2006/04/metadata'
Q = lambda name: f'{{{NS}}}{name}'
ET.register_namespace('', NS)


def api_version(project_root):
    source = Path(project_root)/'sfdx-project.json'
    if not source.is_file():
        raise ValueError('Flow generation requires sfdx-project.json in the project root.')
    version = str(json.loads(source.read_text(encoding='utf-8')).get('sourceApiVersion', ''))
    if not re.fullmatch(r'\d{2}\.0', version) or float(version) < 50:
        raise ValueError('Flow v1 requires sourceApiVersion >= 50.0 in sfdx-project.json.')
    return version


def text(parent, name, value):
    ET.SubElement(parent, Q(name)).text = str(value)


def connector(parent, name, target):
    if target is not None:
        text(ET.SubElement(parent, Q(name)), 'targetReference', target)


def literal(parent, name, value):
    node = ET.SubElement(parent, Q(name))
    if isinstance(value, FlowRecordReference):
        text(node, 'elementReference', value.value)
        return
    tag = {'String':'stringValue', 'Number':'numberValue', 'Boolean':'booleanValue', 'Date':'dateValue', 'DateTime':'dateTimeValue'}[value.type]
    text(node, tag, str(value.value).lower() if value.type == 'Boolean' else value.value)


def flow_xml(item, version):
    config = validate_flow(item.fullName, item.label, item.config)
    if isinstance(config, ExtendedFlowConfig):
        return extended_flow_xml(item, version, config)
    root = ET.Element(Q('Flow'))
    text(root, 'apiVersion', version)
    # Metadata uses grouped node collections, independent of execution order.
    for kind, tag in [('Assignment','assignments'),('Decision','decisions'),('CreateRecords','recordCreates'),('UpdateRecords','recordUpdates')]:
        for index, element in enumerate(config.elements):
            if element.kind != kind: continue
            node = ET.SubElement(root, Q(tag))
            for key,value in [('name',element.name),('label',element.label),('locationX',176),('locationY',176+index*160)]:
                text(node,key,value)
            if isinstance(element,FlowAssignment):
                for assignment in element.assignments:
                    entry = ET.SubElement(node,Q('assignmentItems'))
                    text(entry,'assignToReference',assignment.field)
                    text(entry,'operator','Assign')
                    literal(entry,'value',assignment.value)
                connector(node,'connector',element.next)
            elif isinstance(element, FlowDecision):
                connector(node,'defaultConnector',element.defaultNext)
                text(node,'defaultConnectorLabel',element.defaultLabel)
                for rule in element.rules:
                    entry=ET.SubElement(node,Q('rules'))
                    text(entry,'name',rule.name)
                    text(entry,'conditionLogic',rule.conditionLogic)
                    for condition in rule.conditions:
                        clause=ET.SubElement(entry,Q('conditions'))
                        text(clause,'leftValueReference',condition.field)
                        text(clause,'operator',condition.operator)
                        literal(clause,'rightValue',condition.value)
                    connector(entry,'connector',rule.next)
                    text(entry,'label',rule.label)
            else:
                connector(node,'connector',element.next)
                connector(node,'faultConnector',element.faultNext)
                if isinstance(element,FlowUpdateRecords):
                    self_update = element.object == config.object
                    if self_update:
                        # Id + user filters are mandatory. Any unequal/null target
                        # triggers the write; when all values match, no DML occurs.
                        base_count = 1 + len(element.filters)
                        required = ' AND '.join(str(i) for i in range(1,base_count+1))
                        changed = ' OR '.join(str(i) for i in range(base_count+1,base_count+2*len(element.inputAssignments)+1))
                        text(node,'filterLogic', required + ' AND (' + changed + ')')
                    else:
                        text(node,'filterLogic','and')
                    anchor=ET.SubElement(node,Q('filters'))
                    text(anchor,'field',element.relationshipField)
                    text(anchor,'operator','EqualTo')
                    literal(anchor,'value',FlowRecordReference(type='Reference',value='$Record.Id'))
                    for condition in element.filters:
                        clause=ET.SubElement(node,Q('filters'))
                        text(clause,'field',condition.field)
                        text(clause,'operator',condition.operator)
                        literal(clause,'value',condition.value)
                    if self_update:
                        for assignment in element.inputAssignments:
                            for operator,value in [('NotEqualTo',assignment.value),('IsNull',FlowValue(type='Boolean',value=True))]:
                                clause=ET.SubElement(node,Q('filters'))
                                text(clause,'field',assignment.field)
                                text(clause,'operator',operator)
                                literal(clause,'value',value)
                for assignment in element.inputAssignments:
                    entry=ET.SubElement(node,Q('inputAssignments'))
                    text(entry,'field',assignment.field)
                    literal(entry,'value',assignment.value)
                text(node,'object',element.object)
    if item.description: text(root,'description',item.description)
    for resource in config.formulas:
        node=ET.SubElement(root,Q('formulas'))
        text(node,'name',resource.name)
        text(node,'dataType',resource.dataType)
        text(node,'expression',resource.expression)
        if resource.dataType == 'Number': text(node,'scale',resource.scale)
    text(root,'interviewLabel',item.label+' {!$Flow.CurrentDateTime}')
    text(root,'label',item.label)
    text(root,'processType','AutoLaunchedFlow')
    # Preserve Metadata API field order: record collections follow processType.
    for tag in ('recordCreates','recordUpdates'):
        for node in list(root.findall(Q(tag))):
            root.remove(node)
            root.append(node)
    start=ET.SubElement(root,Q('start'))
    text(start,'locationX',50)
    text(start,'locationY',0)
    connector(start,'connector',config.startElement)
    text(start,'object',config.object)
    text(start,'recordTriggerType',config.recordTriggerType)
    text(start,'triggerType',config.triggerType)
    text(root,'status','Draft')
    for resource in config.variables:
        node=ET.SubElement(root,Q('variables'))
        text(node,'name',resource.name)
        text(node,'dataType',resource.dataType)
        text(node,'isCollection','false')
        text(node,'isInput','false')
        text(node,'isOutput','false')
        if resource.dataType == 'Number': text(node,'scale',resource.scale)
        literal(node,'value',resource.value)
    return root


def generate_flow(item, project_root):
    root=flow_xml(item,api_version(project_root))
    from Backend.AI.app.services.metadata_safety import component_path, safe_source_target
    path=safe_source_target(project_root,component_path('Flow',item.fullName).as_posix())
    path.parent.mkdir(parents=True,exist_ok=True)
    ET.indent(root,space='    ')
    ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
    return path


def _canonical(root):
    for node in root.iter():
        if len(node) and node.text is not None and not node.text.strip(): node.text=None
        node.tail=None
    return ET.tostring(root)


def validate_flow_artifact(path, item, project_root):
    """Match staged XML to the approved graph, including status and assignments."""
    try:
        actual=ET.parse(path).getroot()
    except (ET.ParseError,OSError) as exc:
        raise ValueError(f'Cannot read Flow XML: {Path(path).name}') from exc
    expected=flow_xml(item,api_version(project_root))
    if _canonical(actual) != _canonical(expected):
        raise ValueError(f'Flow XML does not match approved Draft configuration: {item.fullName}')


def extended_flow_xml(item,version,config):
    from Backend.AI.app.validators.flow_validator import (
        DeleteRecord, FlowLoopNode, FlowCollectionAssignment, ActionNode, SubflowNode, RecordCollectionOperation,
    )
    root=ET.Element(Q('Flow'))
    def base(tag,node,index=0):
        xml=ET.SubElement(root,Q(tag))
        for key,value in [('name',node.name),('label',node.label),('locationX',176),('locationY',176+index*160)]: text(xml,key,value)
        return xml
    def conditions(xml,values):
        for c in values:
            entry=ET.SubElement(xml,Q('conditions'));text(entry,'leftValueReference',c.field);text(entry,'operator',c.operator);literal(entry,'rightValue',c.value)
    def filters(xml,values):
        for f in values:
            entry=ET.SubElement(xml,Q('filters'));text(entry,'field',f.field);text(entry,'operator',f.operator);literal(entry,'value',f.value)
    for i,n in enumerate(config.elements):
        if not isinstance(n,ActionNode):continue
        xml=base('actionCalls',n,i);text(xml,'actionName',n.actionName);text(xml,'actionType',n.actionType)
        connector(xml,'connector',n.next);connector(xml,'faultConnector',n.faultNext)
        for arg in n.inputs:
            entry=ET.SubElement(xml,Q('inputParameters'));text(entry,'name',arg.name);literal(entry,'value',arg.value)
        for arg in n.outputs:
            entry=ET.SubElement(xml,Q('outputParameters'));text(entry,'assignToReference',arg.variable);text(entry,'name',arg.name)
        text(xml,'storeOutputAutomatically','false')
    text(root,'apiVersion',version)
    for i,n in enumerate(config.elements):
        if not isinstance(n,(FlowAssignment,FlowCollectionAssignment)):continue
        xml=base('assignments',n,i)
        entries=[(a.field,'Assign',a.value) for a in n.assignments] if isinstance(n,FlowAssignment) else [(n.collection,n.operator,n.value)]
        for target,operator,value in entries:
            entry=ET.SubElement(xml,Q('assignmentItems'));text(entry,'assignToReference',target);text(entry,'operator',operator);literal(entry,'value',value)
        connector(xml,'connector',n.next)
    for c in config.choices:
        xml=ET.SubElement(root,Q('choices'));text(xml,'name',c.name);text(xml,'choiceText',c.choiceText);text(xml,'dataType',c.dataType);literal(xml,'value',c.value)
    for c in config.constants:
        xml=ET.SubElement(root,Q('constants'));text(xml,'name',c.name);text(xml,'dataType',c.dataType);literal(xml,'value',c.value)
    for i,n in enumerate(config.elements):
        if not isinstance(n,FlowDecision):continue
        xml=base('decisions',n,i);connector(xml,'defaultConnector',n.defaultNext);text(xml,'defaultConnectorLabel',n.defaultLabel)
        for rule in n.rules:
            entry=ET.SubElement(xml,Q('rules'));text(entry,'name',rule.name);text(entry,'conditionLogic',rule.conditionLogic);conditions(entry,rule.conditions);connector(entry,'connector',rule.next);text(entry,'label',rule.label)
    if item.description:text(root,'description',item.description)
    for choice in config.dynamicChoices:
        xml=ET.SubElement(root,Q('dynamicChoiceSets'));text(xml,'name',choice.name);text(xml,'dataType',choice.metadata_data_type)
        if choice.mode=='Picklist':
            text(xml,'picklistField',choice.picklistField);text(xml,'picklistObject',choice.object)
        else:
            text(xml,'displayField',choice.displayField);text(xml,'filterLogic','and');filters(xml,choice.filters);text(xml,'limit',choice.limit);text(xml,'object',choice.object);text(xml,'sortField','Id');text(xml,'sortOrder','Asc');text(xml,'valueField',choice.valueField)
    for f in [*config.formulas,*config.expressions]:
        xml=ET.SubElement(root,Q('formulas'));text(xml,'name',f.name);text(xml,'dataType',f.dataType);text(xml,'expression',f.expression)
        if f.dataType=='Number':text(xml,'scale',f.scale)
    text(root,'interviewLabel',item.label+' {!$Flow.CurrentDateTime}');text(root,'label',item.label)
    for i,n in enumerate(config.elements):
        if not isinstance(n,FlowLoopNode):continue
        xml=base('loops',n,i);text(xml,'assignNextValueToReference',n.currentItem);text(xml,'collectionReference',n.collection);text(xml,'iterationOrder',n.iterationOrder)
        connector(xml,'nextValueConnector',n.nextValue);connector(xml,'noMoreValuesConnector',n.next)
    text(root,'processType','Flow' if config.flowType=='Screen' else 'AutoLaunchedFlow')
    for tag,cls in [('recordCreates',CreateRecord),('recordDeletes',DeleteRecord),('recordLookups',GetRecords),('recordUpdates',UpdateRecord)]:
        for i,n in enumerate(config.elements):
            bulk=isinstance(n,RecordCollectionOperation) and tag=={'Create':'recordCreates','Update':'recordUpdates','Delete':'recordDeletes'}[n.operation]
            if not isinstance(n,cls) and not bulk:continue
            xml=base(tag,n,i)
            if bulk:
                connector(xml,'connector',n.next);connector(xml,'faultConnector',n.faultNext);text(xml,'inputReference',n.inputReference);continue
            if isinstance(n,GetRecords):text(xml,'assignNullValuesIfNoRecordsFound','true')
            if isinstance(n,CreateRecord) and n.assignRecordIdTo:text(xml,'assignRecordIdToReference',n.assignRecordIdTo)
            connector(xml,'connector',n.next);connector(xml,'faultConnector',n.faultNext)
            if isinstance(n,GetRecords):
                text(xml,'filterLogic','and');filters(xml,n.filters);text(xml,'getFirstRecordOnly',str(n.getFirstRecordOnly).lower());text(xml,'object',n.object)
                for out in n.outputAssignments:
                    entry=ET.SubElement(xml,Q('outputAssignments'));text(entry,'assignToReference',out.variable);text(entry,'field',out.field)
                if n.outputReference:text(xml,'outputReference',n.outputReference)
                for name in n.queriedFields:text(xml,'queriedFields',name)
                text(xml,'sortField','Id');text(xml,'sortOrder','Asc');text(xml,'storeOutputAutomatically','false');continue
            if isinstance(n,(UpdateRecord,DeleteRecord)):
                text(xml,'filterLogic','and');entry=ET.SubElement(xml,Q('filters'));text(entry,'field','Id');text(entry,'operator','EqualTo');literal(entry,'value',n.recordId)
            for a in getattr(n,'inputAssignments',[]):
                entry=ET.SubElement(xml,Q('inputAssignments'));text(entry,'field',a.field);literal(entry,'value',a.value)
            text(xml,'object',n.object)
    for i,n in enumerate(config.elements):
        if not isinstance(n,ScreenNode):continue
        xml=base('screens',n,i)
        for name in ['allowBack','allowFinish','allowPause']:text(xml,name,str(getattr(n,name)).lower())
        if n.backButtonLabel:text(xml,'backButtonLabel',n.backButtonLabel)
        connector(xml,'connector',n.next)
        for f in n.fields:
            entry=ET.SubElement(xml,Q('fields'));text(entry,'name',f.name)
            for name in f.choiceReferences:text(entry,'choiceReferences',name)
            if f.dataType:text(entry,'dataType',f.dataType)
            if f.defaultSelectedChoiceReference:text(entry,'defaultSelectedChoiceReference',f.defaultSelectedChoiceReference)
            if f.defaultValue:literal(entry,'defaultValue',f.defaultValue)
            if f.extensionName:text(entry,'extensionName',f.extensionName)
            text(entry,'fieldText',f.fieldText);text(entry,'fieldType',f.fieldType)
            if f.helpText:text(entry,'helpText',f.helpText)
            for arg in f.inputParameters:
                param=ET.SubElement(entry,Q('inputParameters'));text(param,'name',arg.name);literal(param,'value',arg.value)
            if f.fieldType not in {'DisplayText','ComponentInstance'}:text(entry,'isRequired',str(f.isRequired).lower())
            for arg in f.outputParameters:
                param=ET.SubElement(entry,Q('outputParameters'));text(param,'assignToReference',arg.variable);text(param,'name',arg.name)
            if f.dataType in {'Number','Currency'}:text(entry,'scale',f.scale)
            if f.fieldType=='ComponentInstance':text(entry,'storeOutputAutomatically','false')
            if f.validationRule:
                rule=ET.SubElement(entry,Q('validationRule'));text(rule,'errorMessage',f.validationRule.errorMessage);text(rule,'formulaExpression',f.validationRule.formulaExpression)
            if f.visibilityRule:
                rule=ET.SubElement(entry,Q('visibilityRule'));text(rule,'conditionLogic',f.visibilityRule.conditionLogic);conditions(rule,f.visibilityRule.conditions)
        if n.nextOrFinishButtonLabel:text(xml,'nextOrFinishButtonLabel',n.nextOrFinishButtonLabel)
        if n.pauseButtonLabel:text(xml,'pauseButtonLabel',n.pauseButtonLabel)
        text(xml,'showFooter',str(n.showFooter).lower());text(xml,'showHeader',str(n.showHeader).lower())
    start=ET.SubElement(root,Q('start'));text(start,'locationX',50);text(start,'locationY',0);connector(start,'connector',config.startElement)
    if config.doesRequireRecordChangedToMeetCriteria:text(start,'doesRequireRecordChangedToMeetCriteria','true')
    if config.startFilters:text(start,'filterLogic','and');filters(start,config.startFilters)
    if config.object:text(start,'object',config.object)
    if config.recordTriggerType:text(start,'recordTriggerType',config.recordTriggerType)
    if config.schedule:
        schedule=ET.SubElement(start,Q('schedule'));utc=config.schedule.utc_start()
        text(schedule,'frequency',config.schedule.frequency);text(schedule,'startDate',utc.date().isoformat());text(schedule,'startTime',utc.strftime('%H:%M:%S.000Z'))
    for path in config.scheduledPaths:
        entry=ET.SubElement(start,Q('scheduledPaths'));text(entry,'name',path.name);connector(entry,'connector',path.next);text(entry,'label',path.label)
        if path.offsetNumber is not None:text(entry,'offsetNumber',path.offsetNumber)
        if path.offsetUnit:text(entry,'offsetUnit',path.offsetUnit)
        if path.pathType:text(entry,'pathType',path.pathType)
        if path.recordField:text(entry,'recordField',path.recordField)
        if path.timeSource:text(entry,'timeSource',path.timeSource)
    if config.triggerType:text(start,'triggerType',config.triggerType)
    text(root,'status','Draft')
    for i,n in enumerate(config.elements):
        if not isinstance(n,SubflowNode):continue
        if n.flowName==item.fullName:raise ValueError('A Flow cannot call itself as a subflow.')
        xml=base('subflows',n,i);connector(xml,'connector',n.next);text(xml,'flowName',n.flowName)
        for arg in n.inputs:
            entry=ET.SubElement(xml,Q('inputAssignments'));text(entry,'name',arg.name);literal(entry,'value',arg.value)
        for arg in n.outputs:
            entry=ET.SubElement(xml,Q('outputAssignments'));text(entry,'assignToReference',arg.variable);text(entry,'name',arg.name)
        text(xml,'storeOutputAutomatically','false')
    for t in config.textTemplates:
        xml=ET.SubElement(root,Q('textTemplates'));text(xml,'name',t.name);text(xml,'isViewedAsPlainText',str(t.isViewedAsPlainText).lower());text(xml,'text',t.text)
    for var in config.variables:
        entry=ET.SubElement(root,Q('variables'));text(entry,'name',var.name);text(entry,'dataType',var.dataType)
        text(entry,'isCollection',str(var.isCollection).lower());text(entry,'isInput',str(var.isInput).lower());text(entry,'isOutput',str(var.isOutput).lower())
        if var.objectType:text(entry,'objectType',var.objectType)
        if var.dataType=='Number':text(entry,'scale',var.scale)
        if var.value is not None:literal(entry,'value',var.value)
    return root
