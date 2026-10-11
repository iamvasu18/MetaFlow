"""Translate a bounded, typed subset of org formulas, before plan approval.

No eval, AI-generated expression, or regex-only substitution. Unknown syntax,
relationships, globals, blank-sensitive numeric dependencies and unavailable
system fields fail closed. Fresh describe metadata is checked at deployment.
"""
from copy import deepcopy
from hashlib import sha256
import json
import re
from types import SimpleNamespace

TOKEN = re.compile(r'\s*(?:(\d+(?:\.\d+)?)|("(?:[^"\\]|\\["\\])*")|([A-Za-z][A-Za-z0-9_]*)|(>=|<=|<>|!=|==|&&|\|\||[()+\-*/&,=<>]))')
TYPES = {'double':'Number','number':'Number','int':'Number','integer':'Number',
         'boolean':'Boolean','checkbox':'Boolean','string':'String','text':'String',
         'date':'Date','datetime':'DateTime'}


def check_field_available(name, field, config):
    if getattr(config, 'triggerType', None) != 'RecordBeforeSave': return
    if name in {'LastModifiedDate','SystemModstamp'} or field.get('autoNumber'):
        raise ValueError(f'Before-save dependency {name} requires a value populated after save; use a supported after-save design.')
    if getattr(config, 'recordTriggerType', None) != 'Update' and name in {'Id','CreatedDate','CreatedById'}:
        raise ValueError(f'Before-save CREATE dependency {name} is unavailable. Choose a user-entered date or an after-save design; no substitute date is invented.')


class FormulaCompiler:
    def __init__(self, fields, config):
        self.fields = {f['name']:f for f in fields if f.get('name')}
        self.config = config
        self.stack = []
        self.used = {}
        self.expansions = 0

    def field(self, name):
        field = self.fields.get(name)
        if field is None: raise ValueError(f'Formula dependency is unknown or inaccessible: {name}.')
        check_field_available(name, field, self.config)
        keys = ('name','type','calculated','calculatedFormula','scale','nillable','autoNumber')
        self.used[name] = {k:field.get(k) for k in keys}
        typ = TYPES.get(str(field.get('type','')).lower())
        if typ is None:
            raise ValueError(f'Unsupported formula dependency type: {name} ({field.get("type")}). Currency/Percent conversion and picklist semantics require additional support.')
        if field.get('calculated'):
            if name in self.stack: raise ValueError('Cyclic formula dependencies are unsupported.')
            if len(self.stack) >= 12: raise ValueError('Formula dependency nesting limit exceeded.')
            self.expansions += 1
            if self.expansions > 80: raise ValueError('Formula expansion limit exceeded.')
            expression = field.get('calculatedFormula')
            if not isinstance(expression,str) or not expression.strip():
                raise ValueError(f'Formula definition unavailable for {name}; refresh org metadata or check metadata access.')
            self.stack.append(name)
            result_type, rendered = self.parse(expression)
            self.stack.pop()
            if result_type != typ: raise ValueError(f'Formula return type mismatch for {name}.')
            if typ == 'Number':
                scale = field.get('scale')
                if type(scale) is not int or not 0 <= scale <= 17:
                    raise ValueError(f'Formula numeric scale unavailable/unsupported for {name}.')
                # Carry scale on the resource; do not invent ROUND calls or
                # round nested formulas before the source expression does.
            if len(rendered)>3900: raise ValueError('Expanded Flow formula exceeds 3900 characters.')
            return typ, rendered
        # Describe lacks the source formula's blank-handling policy. Never assume 0.
        if typ == 'Number' and field.get('nillable') is not False:
            raise ValueError(f'Nullable numeric formula dependency {name} needs verified blank-field handling; automatic translation is not supported yet.')
        return typ, '{!$Record.' + name + '}'

    def parse(self, expression):
        if any(ord(c)<32 and c not in '\t\r\n' for c in expression):
            raise ValueError('Formula contains XML control characters.')
        if len(expression)>3900: raise ValueError('Source formula exceeds supported length.')
        tokens=[];pos=0
        while pos<len(expression.rstrip()):
            match=TOKEN.match(expression,pos)
            if not match:
                raise ValueError('Unsupported formula syntax: relationship paths, globals, comments and unknown tokens require an explicitly supported design.')
            tokens.append((match.lastindex, match.group(match.lastindex)))
            pos=match.end()
        if len(tokens)>500: raise ValueError('Formula token limit exceeded.')
        parser=_Parser(tokens,self)
        result=parser.expression()
        if parser.index != len(tokens): raise ValueError('Unsupported trailing formula syntax.')
        return result


class _Parser:
    precedence={'||':1,'&&':2,'=':3,'==':3,'!=':3,'<>':3,'<':3,'>':3,'<=':3,'>=':3,'&':4,'+':5,'-':5,'*':6,'/':6}
    def __init__(self,tokens,compiler): self.tokens=tokens;self.index=0;self.compiler=compiler;self.depth=0
    def peek(self): return self.tokens[self.index][1] if self.index<len(self.tokens) else None
    def take(self):
        if self.index>=len(self.tokens): raise ValueError('Incomplete formula expression.')
        token=self.tokens[self.index];self.index+=1;return token
    def expect(self,value):
        if self.take()[1]!=value: raise ValueError(f'Formula expected {value}.')
    def expression(self,minimum=0):
        self.depth+=1
        if self.depth>40: raise ValueError('Formula expression nesting limit exceeded.')
        left=self.atom()
        while self.peek() in self.precedence and self.precedence[self.peek()]>=minimum:
            op=self.take()[1];right=self.expression(self.precedence[op]+1)
            a,b=left[0],right[0]
            if op in {'&&','||'} and a==b=='Boolean': typ='Boolean'
            elif op in {'=','==','!=','<>','<','>','<=','>='} and a==b and (op in {'=','==','!=','<>'} or a in {'Number','Date','DateTime'}): typ='Boolean'
            elif op=='&' and a==b=='String': typ='String'
            elif op in {'+','-','*','/'} and a==b=='Number': typ='Number'
            elif op=='-' and a==b and a in {'Date','DateTime'}: typ='Number'
            elif op in {'+','-'} and a in {'Date','DateTime'} and b=='Number': typ=a
            else: raise ValueError(f'Unsupported formula operands: {a} {op} {b}.')
            left=(typ,f'({left[1]} {op} {right[1]})')
        self.depth-=1
        return left
    def atom(self):
        kind,value=self.take()
        if value=='(':
            result=self.expression();self.expect(')');return result
        if value in {'+','-'}:
            typ,rendered=self.expression(7)
            if typ!='Number': raise ValueError('Unary sign requires Number.')
            return typ,f'({value}{rendered})'
        if kind==1: return 'Number',value
        if kind==2: return 'String',value
        if kind!=3: raise ValueError('Expected formula field, literal or function.')
        if self.peek()!='(':
            if value.upper() in {'TRUE','FALSE'}: return 'Boolean',value.upper()
            return self.compiler.field(value)
        self.take();args=[]
        if self.peek()!=')':
            while True:
                args.append(self.expression())
                if self.peek()!=',': break
                self.take()
        self.expect(')')
        function=value.upper();types=[x[0] for x in args];count=len(args)
        typ=None
        if function in {'TODAY','NOW'} and count==0: typ='Date' if function=='TODAY' else 'DateTime'
        elif function in {'TRUE','FALSE'} and count==0: typ='Boolean'
        elif function=='DATEVALUE' and types==['DateTime']: typ='Date'
        elif function=='DATE' and types==['Number']*3: typ='Date'
        elif function in {'YEAR','MONTH','DAY'} and types==['Date']: typ='Number'
        elif function=='ISBLANK' and count==1: typ='Boolean'
        elif function=='IF' and count==3 and types[0]=='Boolean' and types[1]==types[2]: typ=types[1]
        elif function=='BLANKVALUE' and count==2 and types[0]==types[1]: typ=types[0]
        elif function in {'AND','OR'} and count>=1 and set(types)=={'Boolean'}: typ='Boolean'
        elif function=='NOT' and types==['Boolean']: typ='Boolean'
        elif function in {'ABS','FLOOR','CEILING'} and types==['Number']: typ='Number'
        elif function=='ROUND' and types==['Number','Number']: typ='Number'
        elif function in {'MIN','MAX'} and count>=1 and set(types)=={'Number'}: typ='Number'
        elif function=='LEN' and types==['String']: typ='Number'
        if typ is None: raise ValueError(f'Unsupported formula function or argument types: {function}({", ".join(types)}).')
        return typ,function+'('+', '.join(x[1] for x in args)+')'


def compile_field_formula(name,fields,config):
    compiler=FormulaCompiler(fields,config)
    source=compiler.fields.get(name)
    if not source or source.get('calculated') is not True:
        raise ValueError(f'Formula resource source must be an existing calculated field: {name}.')
    typ,expression=compiler.field(name)
    digest=sha256(json.dumps(compiler.used,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'sourceField':name,'dataType':typ,'expression':expression,
            'scale':source['scale'] if typ=='Number' else 0,'sourceFingerprint':digest}


def resolve_plan_formulas(plan_data,context):
    """Resolve draft formula requests and before-save field reads; never mutate input.

    AI supplies ordinary field references. Resources are derived from org metadata.
    Draft resource requests are rebuilt from org metadata, never AI expressions.
    Approved resources must match the deterministic compiler exactly.
    """
    data=deepcopy(plan_data)
    objects={o.get('name'):o for o in context.get('objects',[])}
    for item in data.get('items',[]):
        if not isinstance(item,dict) or item.get('metadataType')!='Flow' or item.get('action')!='CREATE': continue
        config=item.get('config',{})
        if not isinstance(config,dict): continue
        if config.get('triggerType') not in {'RecordBeforeSave','RecordAfterSave','RecordBeforeDelete','Scheduled','PlatformEvent'}: continue
        draft = data.get('status', 'DRAFT') == 'DRAFT' and item.get('approval', 'PENDING') == 'PENDING'
        if draft and config.get('triggerType') == 'RecordAfterSave':
            for node in config.get('elements', []):
                if isinstance(node, dict) and node.get('kind') == 'UpdateRecords' and node.get('object') == config.get('object'):
                    node.setdefault('relationshipField', 'Id')
        fields=objects.get(config.get('object'),{}).get('fields',[])
        by_name={f.get('name'):f for f in fields}
        formulas=config.get('formulas',[])
        if not isinstance(formulas,list): raise ValueError('Flow formulas must be a list.')
        # Independent calculations belong to contract v2 expressions, not the
        # deterministic compiler for existing Salesforce calculated fields.
        retained=[]
        for resource in formulas:
            source=resource.get('sourceField') if isinstance(resource,dict) else None
            simple=source.split('.')[-1] if isinstance(source,str) else None
            field=by_name.get(simple)
            if draft and field and not field.get('calculated') and resource.get('expression'):
                if not resource.get('dataType'):
                    raise ValueError('Independent Flow calculation requires an explicit dataType.')
                config.setdefault('expressions',[]).append({k:resource[k] for k in ('name','dataType','expression','scale') if k in resource})
                config['contractVersion']=2
            else:
                retained.append(resource)
        formulas=retained
        config['formulas']=formulas
        used={n.get('name') for n in config.get('elements',[]) if isinstance(n,dict)}
        used.update(r.get('name') for n in config.get('elements',[]) for r in n.get('rules',[]) if isinstance(r,dict))
        used.update(r.get('name') for r in config.get('variables',[]) if isinstance(r,dict))
        used.update(r.get('name') for r in formulas if isinstance(r,dict))
        by_source={}
        for resource in formulas:
            if not isinstance(resource,dict): raise ValueError('Invalid formula resource.')
            source = resource.get('sourceField')
            if draft:
                if not isinstance(source, str):
                    raise ValueError('Formula resource requires an actual sourceField from org metadata.')
                # Only the selected trigger object or $Record may qualify a field.
                for prefix in ('$Record.', str(config.get('object')) + '.'):
                    if source.startswith(prefix):
                        source = source[len(prefix):]
                        break
                if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', source):
                    raise ValueError('Formula sourceField must belong to the triggering object; relationship paths are unsupported.')
            expected=compile_field_formula(source,fields,SimpleNamespace(**config))
            if draft:
                name = resource.get('name')
                # These are unapproved AI suggestions. Discard generated expressions,
                # fingerprints, type and scale; all are derived from actual org data.
                resource.clear()
                resource.update(name=name, **expected)
            elif {k:v for k,v in resource.items() if k!='name'}!=expected:
                raise ValueError('AI formula resource differs from verified org metadata.')
            by_source[resource['sourceField']]=resource['name']
        def resolve(reference):
            if config.get('triggerType') != 'RecordBeforeSave': return reference
            if not isinstance(reference,str) or not reference.startswith('$Record.'): return reference
            name=reference.split('.',1)[1]
            if not by_name.get(name,{}).get('calculated'): return reference
            if name not in by_source:
                resource=compile_field_formula(name,fields,SimpleNamespace(**config))
                index=1
                while f'Formula_{index}' in used: index+=1
                resource['name']=f'Formula_{index}';used.add(resource['name'])
                formulas.append(resource);by_source[name]=resource['name']
            return by_source[name]
        for node in config.get('elements',[]):
            if node.get('kind')=='Decision':
                for rule in node.get('rules',[]):
                    for condition in rule.get('conditions',[]):
                        condition['field']=resolve(condition.get('field'))
                        value=condition.get('value',{})
                        if value.get('type')=='Reference': value['value']=resolve(value.get('value'))
            elif node.get('kind')=='Assignment':
                for assignment in node.get('assignments',[]):
                    value=assignment.get('value',{})
                    if value.get('type')=='Reference': value['value']=resolve(value.get('value'))
        if formulas: config['formulas']=formulas
    return data
