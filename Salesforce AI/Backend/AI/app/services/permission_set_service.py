"""Strict, additive Permission Set creation and separately confirmed assignment."""
import re
import xml.etree.ElementTree as ET
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from Backend.AI.app.services.metadata_safety import component_path, safe_source_target, validate_component_name

Name = Annotated[str, Field(pattern=r'^[A-Za-z][A-Za-z0-9_]*$', max_length=80)]
QualifiedField = Annotated[str, Field(pattern=r'^[A-Za-z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*$', max_length=161)]
NS = 'http://soap.sforce.com/2006/04/metadata'

class PermissionSetClarification(ValueError):
    def __init__(self,message,question):
        super().__init__(message)
        self.question=question


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class ObjectAccess(Strict):
    object: Name
    allowRead: StrictBool = False
    allowCreate: StrictBool = False
    allowEdit: StrictBool = False
    allowDelete: StrictBool = False
    viewAllRecords: StrictBool = False
    modifyAllRecords: StrictBool = False

    @model_validator(mode='after')
    def dependencies(self):
        if any((self.allowCreate,self.allowEdit,self.allowDelete,self.viewAllRecords,self.modifyAllRecords)) and not self.allowRead:
            raise ValueError('Object create/edit/delete/view-all/modify-all require read access.')
        if self.modifyAllRecords and not all((self.allowEdit,self.allowDelete,self.viewAllRecords)):
            raise ValueError('Modify All requires explicit edit, delete and View All access.')
        return self

class FieldAccess(Strict):
    field: QualifiedField
    readable: StrictBool = False
    editable: StrictBool = False
    @model_validator(mode='after')
    def dependencies(self):
        if self.editable and not self.readable:raise ValueError('Editable fields require readable=true.')
        return self

class ClassAccess(Strict):
    apexClass: Name
    enabled: StrictBool = True

class SystemAccess(Strict):
    name: Name
    enabled: StrictBool = True

class PermissionSetConfig(Strict):
    objectPermissions: list[ObjectAccess] = Field(default_factory=list,max_length=100)
    fieldPermissions: list[FieldAccess] = Field(default_factory=list,max_length=500)
    classAccesses: list[ClassAccess] = Field(default_factory=list,max_length=100)
    userPermissions: list[SystemAccess] = Field(default_factory=list,max_length=100)
    license: str | None = Field(default=None,max_length=80)

    @model_validator(mode='after')
    def dependencies(self):
        for entries,key in [(self.objectPermissions,'object'),(self.fieldPermissions,'field'),(self.classAccesses,'apexClass'),(self.userPermissions,'name')]:
            names=[getattr(entry,key) for entry in entries]
            if len(names)!=len(set(names)):raise ValueError('Duplicate permission entries are not allowed.')
        objects={entry.object:entry for entry in self.objectPermissions}
        for field in self.fieldPermissions:
            parent=field.field.split('.')[0]; access=objects.get(parent)
            if (field.readable or field.editable) and (not access or not access.allowRead):
                raise ValueError(f'{field.field}: include explicit parent object read access.')
            if field.editable and not access.allowEdit:
                raise ValueError(f'{field.field}: include explicit parent object edit access.')
        return self


def validate_permission_set(name,label,config):
    validate_component_name('PermissionSet',name)
    if len(name)>80:raise ValueError('Permission Set API names must be at most 80 characters.')
    if not isinstance(label,str) or not label.strip() or len(label)>80:raise ValueError('Permission Set label is required and must be at most 80 characters.')
    return PermissionSetConfig.model_validate(config)


def generate_permission_set(item,project_root):
    config=validate_permission_set(item.fullName,item.label,item.config)
    ET.register_namespace('',NS);root=ET.Element('{'+NS+'}PermissionSet')
    def child(parent,name,value):
        ET.SubElement(parent,'{'+NS+'}'+name).text=str(value).lower() if isinstance(value,bool) else str(value)
    for entry in sorted(config.classAccesses,key=lambda e:e.apexClass):
        node=ET.SubElement(root,'{'+NS+'}classAccesses');child(node,'apexClass',entry.apexClass);child(node,'enabled',entry.enabled)
    if item.description:child(root,'description',item.description)
    for entry in sorted(config.fieldPermissions,key=lambda e:e.field):
        node=ET.SubElement(root,'{'+NS+'}fieldPermissions')
        for key in ('editable','field','readable'):child(node,key,getattr(entry,key))
    child(root,'hasActivationRequired',False);child(root,'label',item.label)
    if config.license:child(root,'license',config.license)
    for entry in sorted(config.objectPermissions,key=lambda e:e.object):
        node=ET.SubElement(root,'{'+NS+'}objectPermissions')
        for key in ('allowCreate','allowDelete','allowEdit','allowRead','modifyAllRecords','object','viewAllRecords'):child(node,key,getattr(entry,key))
    for entry in sorted(config.userPermissions,key=lambda e:e.name):
        node=ET.SubElement(root,'{'+NS+'}userPermissions');child(node,'enabled',entry.enabled);child(node,'name',entry.name)
    target=safe_source_target(project_root,component_path('PermissionSet',item.fullName).as_posix());target.parent.mkdir(parents=True,exist_ok=True)
    ET.indent(root);target.write_text(ET.tostring(root,encoding='unicode',xml_declaration=True),encoding='utf-8')
    return target


def source_config(text):
    root=ET.fromstring(text)
    if root.tag!='{'+NS+'}PermissionSet':raise ValueError('Invalid PermissionSet XML root.')
    allowed={'classAccesses','description','fieldPermissions','hasActivationRequired','label','license','objectPermissions','userPermissions'}
    config={}; label=None
    repeated={'classAccesses','fieldPermissions','objectPermissions','userPermissions'}
    seen=set()
    for node in root:
        if not node.tag.startswith('{'+NS+'}'):raise ValueError('PermissionSet elements must use the metadata namespace.')
        name=node.tag.split('}')[-1]
        if name not in allowed:raise ValueError('Unsupported PermissionSet source setting: '+name)
        if name not in repeated and name in seen:raise ValueError('Duplicate PermissionSet source setting: '+name)
        seen.add(name)
        if name in repeated:
            value={}
            for entry in node:
                if not entry.tag.startswith('{'+NS+'}'):raise ValueError('Permission properties must use the metadata namespace.')
                key=entry.tag.split('}')[-1]
                if key in value:raise ValueError('Duplicate permission property.')
                content=entry.text or ''
                if key in {'enabled','readable','editable','allowRead','allowCreate','allowEdit','allowDelete','viewAllRecords','modifyAllRecords'}:
                    if content not in {'true','false'}:raise ValueError('Permission values must be true or false.')
                    content=content=='true'
                value[key]=content
            config.setdefault(name,[]).append(value)
        elif name=='label':label=node.text
        elif name=='license':config['license']=node.text
        elif name=='hasActivationRequired' and node.text!='false':raise ValueError('Session-based activation is not supported in this workflow.')
    return label,PermissionSetConfig.model_validate(config)


def preflight_permission_set(name,label,config,api,plan=None,context=None):
    spec=validate_permission_set(name,label,config)
    if api is None:raise ValueError('Permission Set checks require a connected Salesforce API org.')
    from Backend.AI.app.services.planned_context import context_with_planned_components
    items=(plan or {}).get('items',[])
    permission_item=next((i for i in items if i.get('metadataType')=='PermissionSet' and i.get('fullName')==name),None)
    if permission_item:
        references={e.object for e in spec.objectPermissions}|{e.field for e in spec.fieldPermissions}|{e.field.split('.')[0] for e in spec.fieldPermissions}|{e.apexClass for e in spec.classAccesses}
        for item in items:
            if item.get('action')=='CREATE' and item.get('metadataType') in {'CustomObject','CustomField','ApexClass'} and item.get('fullName') in references and item.get('id') not in permission_item.get('dependencies',[]):
                raise ValueError('Permission Set must declare its same-plan dependency: '+item['fullName'])
    projected=context_with_planned_components(plan or {'items':[]},context or {'objects':[]})
    objects={o['name']:o for o in projected['objects']}
    names={e.object for e in spec.objectPermissions}|{e.field.split('.')[0] for e in spec.fieldPermissions}
    for obj in sorted(names):
        if obj not in objects:objects[obj]=api.describe_object(obj)
    for entry in spec.fieldPermissions:
        parent,member=entry.field.split('.')
        field=next((f for f in objects[parent]['fields'] if f['name']==member),None)
        if field is None:raise PermissionSetClarification('Unknown field in Permission Set: '+entry.field, entry.field + ' was not found in the retrieved object definition. Should we use another existing field, or include its creation with a specified type?')
        if field.get('permissionable') is False:raise PermissionSetClarification('Field does not support FLS entries: '+entry.field, entry.field + ' does not support an explicit FLS entry. Should I omit that entry and preserve the other requested grants?')
        if entry.editable and (field.get('calculated') or field.get('autoNumber')):raise ValueError('Calculated/auto-number field cannot be editable: '+entry.field)
    if spec.classAccesses:
        live={r['fullName'] for r in api.list_components('ApexClass')}
        planned={i['fullName'] for i in (plan or {}).get('items',[]) if i.get('metadataType')=='ApexClass' and i.get('action')=='CREATE'}
        for entry in spec.classAccesses:
            if entry.apexClass not in live|planned:raise PermissionSetClarification('Unknown Apex class in Permission Set: '+entry.apexClass, entry.apexClass + ' was not returned by the accessible Apex inventory. Should we use a different existing class, or include a new class with its implementation requirement?')
    if spec.userPermissions:
        descriptor=api.describe_object('PermissionSet')
        supported={f['name'][len('Permissions'):] for f in descriptor['fields'] if f.get('type')=='boolean' and f['name'].startswith('Permissions')}
        for entry in spec.userPermissions:
            if entry.name not in supported:raise PermissionSetClarification('System permission is not exposed by this org: '+entry.name, entry.name + ' is not exposed by this org/API version. Which supported permission should we use, or should we omit it?')
    if spec.license:
        license_name=spec.license.replace("\\","\\\\").replace("'","\\'")
        if not api.query("SELECT Id FROM UserLicense WHERE Name = '"+license_name+"'")['records']:raise ValueError('Permission Set license is unavailable in this org.')
    return spec


def grant_signature(config):
    """Ignore disabled/default entries, but preserve every enabled grant."""
    return {
        'objects': sorted((e.object,key) for e in config.objectPermissions for key in ('allowRead','allowCreate','allowEdit','allowDelete','viewAllRecords','modifyAllRecords') if getattr(e,key)),
        'fields': sorted((e.field,key) for e in config.fieldPermissions for key in ('readable','editable') if getattr(e,key)),
        'classes': sorted(e.apexClass for e in config.classAccesses if e.enabled),
        'system': sorted(e.name for e in config.userPermissions if e.enabled),
        'license':config.license,
    }


class PermissionAssignmentService:
    def __init__(self,transport):self.transport=transport;self.api=transport.api

    def assign(self,package,name,username,confirmed,save):
        if package.get('state')!='deployed' or package.get('operation')!='deploy':raise ValueError('Deploy this Permission Set before assigning it.')
        if not any(c['metadataType']=='PermissionSet' and c['fullName']==name for c in package['components']):raise ValueError('Permission Set is not in this reviewed package.')
        report=package.get('lastResult',{}).get('result',{})
        if report.get('success') is not True or report.get('done') is not True or report.get('checkOnly') is not False:raise ValueError('A confirmed real deployment is required.')
        successes=report.get('details',{}).get('componentSuccesses',[])
        if isinstance(successes,dict):successes=[successes]
        matches=[r for r in successes if r.get('componentType')=='PermissionSet' and r.get('fullName')==name and r.get('success') is True]
        if len(matches)!=1 or not re.fullmatch(r'0PS[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?',str(matches[0].get('id',''))):raise ValueError('The deployment report does not identify an exact Permission Set ID.')
        permission_id=matches[0]['id']
        username=username.strip()
        if not username or len(username)>320:raise ValueError('Provide the exact active Salesforce username.')
        literal=username.replace('\\','\\\\').replace("'","\\'")
        users=self.api.query("SELECT Id, Username, IsActive FROM User WHERE Username = '"+literal+"'")['records']
        if len(users)!=1 or users[0].get('IsActive') is not True:raise ValueError('One active user with this exact username is required.')
        user_id=users[0].get('Id','')
        if not re.fullmatch(r'005[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?',user_id):raise ValueError('Invalid Salesforce user identity.')
        existing=self.api.query(f"SELECT Id FROM PermissionSetAssignment WHERE PermissionSetId = '{permission_id}' AND AssigneeId = '{user_id}'")['records']
        assignment_key=name+':'+user_id
        if existing:
            result={'state':'assigned','permissionSet':name,'username':username,'alreadyAssigned':True,'message':'Permission Set assignment is already present and confirmed.'}
            package.setdefault('permissionAssignments',{})[assignment_key]=result;save(package);return result
        previous=package.get('permissionAssignments',{}).get(assignment_key,{})
        if previous.get('state')=='unknown':raise ValueError('The previous assignment outcome is unconfirmed. No request was repeated. Inspect Permission Set assignments in Salesforce before retrying.')
        if not confirmed:raise ValueError('Explicit confirmation is required before granting access.')
        # Detect live permission drift before granting access from an approved draft.
        from Backend.AI.app.services.salesforce_metadata_api import element
        nodes=self.transport.call('readMetadata',[element('type','PermissionSet'),element('fullNames',name)])
        records=nodes[0].findall('{'+NS+'}records') if len(nodes)==1 else []
        if len(records)!=1:raise ValueError('Could not verify the deployed Permission Set permissions.')
        record=ET.fromstring(ET.tostring(records[0]));record.tag='{'+NS+'}PermissionSet'
        if record.findtext('{'+NS+'}fullName') != name:raise ValueError('Live Permission Set identity does not match the reviewed component.')
        for node in list(record):
            if node.tag=='{'+NS+'}fullName':record.remove(node)
        # Salesforce may return newer optional permission flags as false even when
        # the reviewed source omitted them. Ignore only disabled unknown boolean flags;
        # enabled or non-boolean unsupported settings still fail closed.
        top_allowed={'classAccesses','description','fieldPermissions','hasActivationRequired','label','license','objectPermissions','userPermissions'}
        nested_allowed={'objectPermissions':{'allowCreate','allowDelete','allowEdit','allowRead','modifyAllRecords','object','viewAllRecords'},
            'fieldPermissions':{'editable','field','readable'},'classAccesses':{'apexClass','enabled'},'userPermissions':{'name','enabled'}}
        for node in list(record):
            key=node.tag.split('}')[-1]
            if key not in top_allowed and not list(node) and node.text=='false':record.remove(node);continue
            for child in list(node):
                if key in nested_allowed and child.tag.split('}')[-1] not in nested_allowed[key] and not list(child) and child.text=='false':node.remove(child)
        _,live=source_config(ET.tostring(record,encoding='unicode'))
        _,approved=source_config(package['files'][component_path('PermissionSet',name).as_posix()])
        if grant_signature(live)!=grant_signature(approved):raise ValueError('Live Permission Set grants differ from the reviewed source. Review the changed permissions before assignment.')
        from Backend.AI.app.services.salesforce_api_client import load_org_tokens,http_pool
        import httpx
        attempt={'state':'unknown','permissionSet':name,'username':username,'message':'Assignment submitted; confirmation pending.'}
        package.setdefault('permissionAssignments',{})[assignment_key]=attempt;save(package)
        saved=load_org_tokens(self.api.owner,self.api.org)
        try:
            response=(self.api.http or http_pool()).post(saved['instance_url']+self.api.base+'/sobjects/PermissionSetAssignment',
                json={'PermissionSetId':permission_id,'AssigneeId':user_id},headers={'Authorization':'Bearer '+saved['access_token'],'Accept':'application/json'})
        except httpx.HTTPError:raise ValueError('Assignment outcome is unconfirmed. No request was automatically retried; check assignments in Salesforce.') from None
        if response.status_code>=500:
            raise ValueError('Assignment outcome is unconfirmed after a server error. No request was automatically retried; check assignments in Salesforce.')
        if response.status_code!=201:
            attempt['state']='failed';attempt['message']='Salesforce rejected the assignment. Check the user license, permissions and dependencies.';save(package)
            raise ValueError(attempt['message'])
        try: result=response.json()
        except ValueError:raise ValueError('Assignment outcome is unconfirmed; check assignments in Salesforce.') from None
        if result.get('success') is not True or not result.get('id'):raise ValueError('Assignment outcome is unconfirmed; check assignments in Salesforce.')
        attempt.update(state='assigned',message='Permission Set assigned to '+username+'.');save(package)
        return attempt
