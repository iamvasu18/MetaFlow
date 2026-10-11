"""Owned Metadata SOAP API; mutation timeouts are never automatically retried."""
import base64
from copy import deepcopy
import io
import logging
import re
import time
import zipfile
import xml.etree.ElementTree as ET
import httpx
from fastapi import HTTPException
from Backend.AI.app.services.salesforce_api_client import SalesforceApiClient,load_org_tokens,http_pool
from Backend.AI.app.services.metadata_safety import source_relative_path,validate_component_name

NS='http://soap.sforce.com/2006/04/metadata'
SOAP='http://schemas.xmlsoap.org/soap/envelope/'
Q=lambda name:'{'+NS+'}'+name
ARRAYS={'componentFailures','componentSuccesses','codeCoverage','codeCoverageWarnings','failures','successes','flowCoverage','flowCoverageWarnings','messages','locations','warnings'}
BOOLS={'done','success','checkOnly','changed','created','deleted','rollbackOnError','ignoreWarnings','runTestsEnabled'}
NUMBERS={'numTestsRun','numFailures','numberComponentErrors','numberComponentsDeployed','numberComponentsTotal','numberTestErrors','numberTestsCompleted','numberTestsTotal','numLocations','numLocationsNotCovered','line','column'}

def xml_value(node):
    if not list(node):
        text=node.text or '';key=node.tag.split('}')[-1]
        if key in BOOLS and text in {'true','false'}:return text=='true'
        if key in NUMBERS and re.fullmatch(r'\d+',text):return int(text)
        return text
    value={}
    for child in node:
        name=child.tag.split('}')[-1];item=xml_value(child)
        if name in ARRAYS:value.setdefault(name,[]).append(item)
        elif name in value:
            if not isinstance(value[name],list):value[name]=[value[name]]
            value[name].append(item)
        else:value[name]=item
    return value

def element(name,text=None):
    node=ET.Element(Q(name))
    if text is not None:node.text=str(text).lower() if isinstance(text,bool) else str(text)
    return node

class SalesforceMetadataApi:
    def __init__(self,owner,org,version,http=None):
        self.api=SalesforceApiClient(owner,org,version,http);self.version=str(version)

    def call(self,method,children,mutation=False):
        if method not in {'listMetadata','readMetadata','deploy','checkDeployStatus','retrieve','checkRetrieveStatus'}:raise ValueError('Unsupported Metadata operation.')
        saved=load_org_tokens(self.api.owner,self.api.org)
        started=time.perf_counter()
        try:
            for attempt in range(2):
                envelope=ET.Element('{'+SOAP+'}Envelope')
                header=ET.SubElement(envelope,'{'+SOAP+'}Header')
                session=ET.SubElement(header,Q('SessionHeader'));ET.SubElement(session,Q('sessionId')).text=saved['access_token']
                body=ET.SubElement(envelope,'{'+SOAP+'}Body');operation=ET.SubElement(body,Q(method))
                operation.extend(deepcopy(children))
                try:
                    response=(self.api.http or http_pool()).post(saved['instance_url']+'/services/Soap/m/'+self.version,
                        content=ET.tostring(envelope,encoding='utf-8',xml_declaration=True),
                        headers={'Content-Type':'text/xml; charset=utf-8','SOAPAction':method},timeout=60)
                except httpx.HTTPError:
                    raise RuntimeError('Salesforce Metadata API outcome is unconfirmed. No operation was retried; inspect saved job or Salesforce Deployment Status before resubmitting.' if mutation else 'Salesforce Metadata API read could not complete.') from None
                if len(response.content)>70*1024*1024:raise RuntimeError('Metadata response exceeded the supported size.')
                try:root=ET.fromstring(response.content)
                except ET.ParseError:raise RuntimeError('Salesforce Metadata API returned unreadable XML; outcome is unconfirmed.' if mutation else 'Salesforce Metadata API returned unreadable XML.') from None
                fault=root.find('.//{'+SOAP+'}Fault')
                code=(fault.findtext('faultcode') or '') if fault is not None else ''
                if (response.status_code==401 or code.split(':')[-1]=='INVALID_SESSION_ID') and attempt==0:
                    saved=self.api._refresh(saved['access_token']);continue
                if fault is not None:
                    message=fault.findtext('faultstring') or 'Request rejected.'
                    for key in ('access_token','refresh_token'):message=message.replace(saved[key],'[redacted]')
                    raise RuntimeError('Salesforce Metadata API rejected '+method+': '+message[:1500])
                if response.status_code!=200:raise RuntimeError('Salesforce Metadata API returned an unexpected HTTP status; outcome is unconfirmed.' if mutation else 'Salesforce Metadata API read failed.')
                reply=root.find('.//'+Q(method+'Response'))
                if reply is None:raise RuntimeError('Salesforce Metadata API response is incomplete; outcome is unconfirmed.' if mutation else 'Salesforce Metadata API response is incomplete.')
                return reply.findall(Q('result'))
        finally:logging.getLogger(__name__).warning('Salesforce transport=metadata-api operation=%s seconds=%.3f',method,time.perf_counter()-started)

    def list_metadata(self,kind):
        if kind not in {'Layout','RecordType','CustomObject','CustomField','ValidationRule','ApexClass','ApexTrigger','Flow','LightningComponentBundle'}:raise ValueError('Unsupported metadata inventory.')
        query=element('queries');query.append(element('type',kind))
        rows=[xml_value(row) for row in self.call('listMetadata',[query,element('asOfVersion',self.version)])]
        if any(not isinstance(r,dict) or not isinstance(r.get('fullName'),str) or not r['fullName'] for r in rows):raise RuntimeError('Metadata inventory is incomplete.')
        # Salesforce listMetadata is capped at 1,000 results; never treat a
        # possibly truncated inventory as proof that a CREATE name is absent.
        if len(rows)>=1000:raise ValueError('Metadata inventory reached the 1,000-result limit. Narrow discovery is required before proceeding.')
        return rows

    def report(self,job):
        if not isinstance(job,str) or not re.fullmatch(r'0Af[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?',job):raise ValueError('Invalid saved Salesforce deployment job ID.')
        rows=self.call('checkDeployStatus',[element('asyncProcessId',job),element('includeDetails',True)])
        if len(rows)!=1:raise RuntimeError('Salesforce deployment status is incomplete.')
        result=xml_value(rows[0])
        if not isinstance(result,dict) or result.get('id')!=job or not isinstance(result.get('done'),bool):raise RuntimeError('Salesforce deployment status is incomplete or belongs to another job.')
        return {'status':1 if result.get('done') and result.get('success') is False else 0,'result':result}

    def deploy(self,bundle,check_only=True):
        archive=metadata_archive(bundle['files'],bundle['apiVersion'])
        options=element('deployOptions')
        for key,value in [('checkOnly',check_only),('ignoreWarnings',False),('rollbackOnError',True)]:options.append(element(key,value))
        tests=bundle.get('testClasses',[])
        for name in tests:
            validate_component_name('ApexClass',name);options.append(element('runTests',name))
        if any('/classes/' in p or '/triggers/' in p for p in bundle['files']) and not tests:
            raise ValueError('Saved Apex test classes are required before submission.')
        options.append(element('singlePackage',True))
        # For metadata-only packages, leave testLevel to Salesforce's org policy.
        # Do not force NoTestRun into a production org.
        if tests:options.append(element('testLevel','RunSpecifiedTests'))
        rows=self.call('deploy',[element('ZipFile',base64.b64encode(archive).decode()),options],mutation=True)
        result=xml_value(rows[0]) if len(rows)==1 else None
        if not isinstance(result,dict) or not re.fullmatch(r'0Af[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?',str(result.get('id',''))):raise RuntimeError('Submission returned no confirmed Salesforce job ID. Inspect Deployment Status; do not automatically resubmit.')
        return {'status':0,'result':{'id':result['id'],'done':False,'status':'Pending','checkOnly':check_only,'transport':'metadata-api'}}

    def retrieve_layouts(self,members,root):
        request=element('retrieveRequest');request.append(element('apiVersion',self.version));request.append(element('singlePackage',True))
        package=element('unpackaged')
        for kind,names in members.items():
            if not names:continue
            node=element('types')
            for name in names:node.append(element('members',name))
            node.append(element('name',kind));package.append(node)
        package.append(element('version',self.version));request.append(package)
        rows=self.call('retrieve',[request],mutation=True)
        value=xml_value(rows[0]) if len(rows)==1 else {}
        job=value.get('id') if isinstance(value,dict) else None
        if not isinstance(job,str) or not re.fullmatch(r'09S[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?',job):raise RuntimeError('Layout retrieve returned no valid job ID.')
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            rows=self.call('checkRetrieveStatus',[element('asyncProcessId',job),element('includeZip',True)])
            value=xml_value(rows[0]) if len(rows)==1 else {}
            if not isinstance(value,dict) or value.get('id')!=job or not isinstance(value.get('done'),bool):raise RuntimeError('Layout retrieve status was incomplete.')
            if value['done']:
                if value.get('success') is not True:raise RuntimeError('Salesforce layout retrieve failed. Check metadata access.')
                import_layout_archive(value.get('zipFile',''),members,root);return
            time.sleep(1)
        raise RuntimeError('Layout retrieval exceeded 120 seconds. No deployment was submitted.')

def owned_metadata_api(org,version,http=None):
    from Backend.AI.app.account_api import current_account
    owner=current_account.get()
    return SalesforceMetadataApi(owner,org,version,http) if owner else None

def metadata_archive(files,version):
    """Convert the supported DX sources into one narrow Metadata API package."""
    if not re.fullmatch(r'\d{2,3}\.0',str(version)):raise ValueError('Invalid API version.')
    output={};objects={};members={};prefix='force-app/main/default/'
    def member(kind,name):members.setdefault(kind,set()).add(name)
    for path,body in sorted(files.items()):
        source_relative_path(path)
        if not path.startswith(prefix):raise ValueError('Unsupported deploy source root.')
        relative=path[len(prefix):];parts=relative.split('/')
        if parts[0]=='objects':
            obj=parts[1];validate_component_name('CustomObject',obj)
            if len(parts)==3 and parts[2]==obj+'.object-meta.xml':
                parsed=ET.fromstring(body)
                if parsed.tag!=Q('CustomObject'):raise ValueError('Invalid object source XML.')
                existing=objects.setdefault(obj,ET.Element(Q('CustomObject')))
                for child in parsed:existing.append(deepcopy(child))
                member('CustomObject',obj)
            elif len(parts)==4 and parts[2] in {'fields','validationRules'}:
                kind='CustomField' if parts[2]=='fields' else 'ValidationRule';suffix='.field-meta.xml' if kind=='CustomField' else '.validationRule-meta.xml'
                if not parts[3].endswith(suffix):raise ValueError('Unsupported object subcomponent source.')
                name=parts[3][:-len(suffix)];validate_component_name(kind,obj+'.'+name)
                child=ET.fromstring(body)
                if child.tag!=Q(kind) or child.findtext(Q('fullName'))!=name:raise ValueError('Object subcomponent identity does not match its source.')
                child.tag=Q(parts[2]);objects.setdefault(obj,ET.Element(Q('CustomObject'))).append(child);member(kind,obj+'.'+name)
            else:raise ValueError('Unsupported object source structure.')
        elif parts[0]=='lwc' and len(parts)==3:
            validate_component_name('LightningComponentBundle',parts[1]);output[relative]=body;member('LightningComponentBundle',parts[1])
        else:
            mapping={'classes':('ApexClass','.cls'),'triggers':('ApexTrigger','.trigger'),'flows':('Flow','.flow-meta.xml'),'layouts':('Layout','.layout-meta.xml'),'profiles':('Profile','.profile-meta.xml')}
            if len(parts)!=2 or parts[0] not in mapping:raise ValueError('Unsupported deploy source type.')
            kind,suffix=mapping[parts[0]];name=parts[1]
            if kind in {'ApexClass','ApexTrigger'}:
                base=name[:-9] if name.endswith('-meta.xml') else name
                if not base.endswith(suffix):raise ValueError('Invalid Apex source path.')
                ident=base[:-len(suffix)];validate_component_name(kind,ident);output[relative]=body;member(kind,ident)
            else:
                if not name.endswith(suffix):raise ValueError('Invalid metadata source path.')
                ident=name[:-len(suffix)]
                if kind=='Layout':
                    from Backend.AI.app.services.page_layout_service import layout_path
                    layout_path(ident)
                elif kind=='Profile':
                    if ident!='Admin':raise ValueError('Only the reviewed Admin overlay is supported.')
                else:validate_component_name(kind,ident)
                parsed=ET.fromstring(body)
                if parsed.tag!=Q(kind):raise ValueError('Metadata XML type mismatch.')
                if kind=='Flow' and parsed.findtext(Q('status'))!='Draft':
                    raise ValueError('Deploy Flows as Draft, then use Activate after successful deployment.')
                output[parts[0]+'/'+ident+('.flow' if kind=='Flow' else '.layout' if kind=='Layout' else '.profile')]=body;member(kind,ident)
    for obj,node in objects.items():
        # CustomObject child elements follow Metadata WSDL ordering. Stable sort
        # preserves field/rule order and emits only reviewed source children.
        node[:]=sorted(node,key=lambda n:('' if n.tag==Q('fullName') else n.tag.split('}')[-1]))
        output['objects/'+obj+'.object']=ET.tostring(node,encoding='unicode')
    package=element('Package')
    for kind,names in sorted(members.items()):
        node=element('types')
        for name in sorted(names):node.append(element('members',name))
        node.append(element('name',kind));package.append(node)
    package.append(element('version',version));output['package.xml']=ET.tostring(package,encoding='unicode')
    if sum(len(body.encode()) for body in output.values())>35*1024*1024:raise ValueError('Deployment package exceeds supported size.')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,body in sorted(output.items()):archive.writestr(name,body)
    return stream.getvalue()

def import_layout_archive(encoded,members,root):
    from Backend.AI.app.services.metadata_safety import safe_source_target
    from Backend.AI.app.services.page_layout_service import layout_path,PROFILE_PATH
    try:data=base64.b64decode(encoded,validate=True)
    except (ValueError,TypeError):raise RuntimeError('Retrieved layout ZIP is invalid.') from None
    expected={'profiles/Admin.profile':PROFILE_PATH.as_posix()}
    expected.update({'layouts/'+name+'.layout':layout_path(name).as_posix() for name in members['Layout']})
    seen=set()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(info.file_size for info in archive.infolist())>50*1024*1024:raise ValueError('Retrieved layout archive exceeds supported size.')
        for info in archive.infolist():
            path=info.filename
            if path.startswith('unpackaged/'):path=path[len('unpackaged/'):]
            if path not in expected:continue  # Never extract unrelated metadata.
            if path in seen:raise ValueError('Duplicate component in retrieved layout archive.')
            seen.add(path);body=archive.read(info);parsed=ET.fromstring(body)
            if parsed.tag!=Q('Profile' if path.startswith('profiles/') else 'Layout'):raise ValueError('Retrieved metadata XML type mismatch.')
            target=safe_source_target(root,expected[path]);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
    if seen!=set(expected):raise RuntimeError('Salesforce did not return all requested profile/layout files.')
