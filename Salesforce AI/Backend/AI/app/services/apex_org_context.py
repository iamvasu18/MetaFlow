"""Read validation-rule metadata into isolated staging; never modify org rules."""
import copy
import json
import re
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

NS = 'http://soap.sforce.com/2006/04/metadata'
NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')

class ApexOrgContext:
    def __init__(self,cli):
        self.cli = cli

    def enrich(self,context,target_org,version):
        context = copy.deepcopy(context)
        objects = {item['name']:item for item in context.get('objects',[])}
        if any(not NAME.fullmatch(name) for name in objects):
            raise ValueError('Invalid discovered object API name.')
        for item in objects.values():
            item['validationRules'] = []
        if not objects:
            context['validationRuleDiscovery'] = {'status':'complete','objects':[],'activeRuleCount':0}
            return context
        records = self.cli(['org','list','metadata','--metadata-type','ValidationRule','--target-org',target_org]).get('result')
        if isinstance(records,dict) and 'fullName' in records:
            records = [records]
        if not isinstance(records,list):
            raise RuntimeError('Cannot list org validation rules; Apex generation stopped.')
        members = set()
        for record in records:
            full_name = record.get('fullName')
            if not isinstance(full_name,str) or '.' not in full_name:
                raise RuntimeError('Unexpected validation-rule metadata name.')
            object_name, rule_name = full_name.split('.',1)
            if object_name in objects:
                if not NAME.fullmatch(rule_name):
                    raise RuntimeError('Unexpected validation-rule API name.')
                members.add(full_name)
        if len(members) > 200:
            raise ValueError('More than 200 validation rules in the requested scope; reduce the object scope.')
        if members:
            with tempfile.TemporaryDirectory(prefix='apex-context-',ignore_cleanup_errors=True) as directory:
                root = Path(directory)
                (root/'force-app').mkdir()
                (root/'sfdx-project.json').write_text(json.dumps({'packageDirectories':[{'path':'force-app','default':True}],'namespace':'','sourceApiVersion':version}),encoding='utf-8')
                args = ['project','retrieve','start','--target-org',target_org,'--wait','10']
                for name in sorted(members):
                    args.extend(['--metadata','ValidationRule:'+name])
                result = self.cli(args,root).get('result',{})
                if not isinstance(result,dict) or result.get('done') is not True or result.get('success') is not True:
                    raise RuntimeError('Validation-rule retrieval did not complete successfully; Apex generation stopped.')
                found = set()
                for path in (root/'force-app').rglob('*.validationRule-meta.xml'):
                    rule = ET.parse(path).getroot()
                    if rule.tag != '{'+NS+'}ValidationRule':
                        raise RuntimeError('Unexpected validation-rule XML root.')
                    # Salesforce source format: objects/Object/validationRules/Rule.xml
                    object_name = path.parent.parent.name
                    rule_name = path.name.removesuffix('.validationRule-meta.xml')
                    member = object_name+'.'+rule_name
                    if member not in members:
                        continue
                    if member in found:
                        raise RuntimeError('Duplicate validation-rule artifact.')
                    found.add(member)
                    active = rule.findtext('{'+NS+'}active')
                    if active not in {'true','false'}:
                        raise RuntimeError('Validation rule has an invalid active flag.')
                    if active == 'true':
                        formula = rule.findtext('{'+NS+'}errorConditionFormula')
                        message = rule.findtext('{'+NS+'}errorMessage')
                        if not formula or not message:
                            raise RuntimeError('Active validation rule is missing its formula/error message.')
                        objects[object_name]['validationRules'].append({
                            'fullName':member,'active':True,'errorConditionFormula':formula,
                            'errorMessage':message,'errorDisplayField':rule.findtext('{'+NS+'}errorDisplayField'),
                            'description':rule.findtext('{'+NS+'}description')})
                if found != members:
                    raise RuntimeError('Validation-rule retrieval was incomplete; Apex generation stopped.')
        count = sum(len(item['validationRules']) for item in objects.values())
        context['validationRuleDiscovery'] = {'status':'complete','objects':sorted(objects),'activeRuleCount':count,
            'otherAutomation':'Triggers, Flows and related objects outside this scope are not inspected.'}
        return context
