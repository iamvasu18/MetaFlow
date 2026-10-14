'use strict';
// Parse and compile source; never import or execute generated JavaScript.
const fs = require('node:fs');
const {parse} = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const {transformSync} = require('@lwc/compiler');
// Included by the locked @lwc/compiler dependency tree.
const {parse:parseTemplate} = require('@lwc/template-compiler');
const postcss = require('postcss');
const {Linter} = require('eslint');
const lwcPlugin = require('@lwc/eslint-plugin-lwc');
const lightningPlugin = require('@salesforce/eslint-plugin-lightning');
const babelESLint = require('@babel/eslint-parser');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const errors = [];
function fail(message) { errors.push(message); }
// Targeted lifecycle checks, not a substitute for component interaction tests.
function checkFormLifecycle(ast) {
 const methods = new Map();
 function scan(node, visit) {
  if (!node || typeof node !== 'object') return;
  if (Array.isArray(node)) { for (const child of node) scan(child, visit); return; }
  visit(node);
  for (const [key, value] of Object.entries(node)) {
   if (!['loc','location','start','end'].includes(key)) scan(value, visit);
  }
 }
 function memberName(node) {
  return node?.type === 'MemberExpression' && !node.computed &&
   node.object.type === 'ThisExpression' ? node.property.name : null;
 }
 scan(ast.program, node => {
  if (node.type !== 'ClassMethod' && node.type !== 'ClassProperty') return;
  if (node.computed || node.key?.type !== 'Identifier') return;
  const reads = new Set(), writes = new Set(), calls = new Set();
  scan(node.body || node.value, item => {
   const name = memberName(item);
   if (name) reads.add(name);
   const written = memberName(item.type === 'AssignmentExpression' ? item.left :
    item.type === 'UpdateExpression' ? item.argument : null);
   if (written) writes.add(written);
   const called = item.type === 'CallExpression' ? memberName(item.callee) : null;
   if (called) calls.add(called);
  });
  methods.set(node.key.name, {reads, writes, calls});
 });
 function dependencies(name, kind, seen = new Set()) {
  if (seen.has(name)) return new Set();
  seen.add(name);
  const result = new Set(kind === 'reads' ? [name] : []);
  const method = methods.get(name);
  if (!method) return result;
  for (const item of method[kind]) {
   result.add(item);
   if (kind === 'reads' && methods.has(item)) {
    for (const dependency of dependencies(item, kind, seen)) result.add(dependency);
   }
  }
  for (const call of method.calls) {
   for (const dependency of dependencies(call, kind, seen)) result.add(dependency);
  }
  return result;
 }
 const parsed = parseTemplate(input.html, {apiVersion:Number(input.apiVersion)});
 function inspect(node, conditions = []) {
  if (!node) return;
  const names = [];
  scan(node.condition, item => { if (item.type === 'Identifier') names.push(item.name); });
  const active = [...conditions, ...names];
  if (/^lightning-record-(view|edit)-form$/.test(node.name || '')) {
   const attributes = [...(node.attributes || []), ...(node.properties || [])];
   if (attributes.some(item => (item.attributeName || item.name) === 'oload')) {
    fail('Record form load handler must use onload, not oload.');
   }
   const handler = node.listeners?.find(item => item.name === 'load')?.handler;
   if (handler?.type === 'Identifier') {
    const writes = dependencies(handler.name, 'writes');
    for (const condition of active) {
     if ([...dependencies(condition, 'reads')].some(name => writes.has(name))) {
      fail('Record form must stay mounted: its load handler changes ancestor condition '+condition+'. Render the spinner alongside the form.');
     }
    }
   }
  }
  for (const child of node.children || []) inspect(child, active);
  if (node.else) inspect(node.else, active);
 }
 inspect(parsed.root);
}
try {
 if(input.tests?.trim()) {
  const testAst=parse(input.tests,{sourceType:'module',plugins:['decorators-legacy','classProperties']});
  let cases=0, assertions=0;
  traverse(testAst,{
   CallExpression(p) {
    const node=p.node;
    if(node.callee.type==='Identifier' && ['test','it'].includes(node.callee.name)) cases++;
    if(node.callee.type==='Identifier' && node.callee.name==='expect') { assertions++; if(['BooleanLiteral','NumericLiteral','StringLiteral','NullLiteral'].includes(node.arguments[0]?.type)) fail('Generated Jest assertions must inspect component behavior, not a constant.'); }
    if(node.callee.type==='MemberExpression' && ['test','it','describe'].includes(node.callee.object?.name) && ['skip','only','todo'].includes(node.callee.property?.name)) fail('Generated Jest tests must not skip or focus cases.');
   },
   ImportDeclaration(p) {
    const module=p.node.source.value;
    if(module==='lwc' || module==='c/'+input.name || module==='@salesforce/sfdx-lwc-jest') return;
    if(module.startsWith('@salesforce/apex/') && Object.prototype.hasOwnProperty.call(input.apexMethods||{},module.slice('@salesforce/apex/'.length))) return;
    if(module.startsWith('lightning/') || module.startsWith('@salesforce/schema/')) return;
    fail('Unverified generated Jest import: '+module);
   }
  });
  if(!cases || !assertions) fail('Generated Jest tests require executable cases and assertions.');
 }
 const ast = parse(input.javascript, {sourceType:'module', plugins:['decorators-legacy','classProperties']});
 checkFormLifecycle(ast);
 const imports = new Map();
 for (const node of ast.program.body) if (node.type === 'ImportDeclaration') for (const spec of node.specifiers) imports.set(spec.local.name,{module:node.source.value, imported:spec.imported?.name});
 const modules = new Set(['lwc','lightning/uiRecordApi','lightning/uiObjectInfoApi','lightning/uiRelatedListApi','lightning/uiListsApi','lightning/navigation','lightning/platformShowToastEvent','lightning/toast']);
 const wireOnly = new Set(['getRecord','getRecords','getRecordUi','getRecordCreateDefaults']);
 function checkParameters(method, argument) {
  const expected=input.apexMethods?.[method]?.parameterNames;
  if (!Array.isArray(expected) || argument?.type !== 'ObjectExpression') return;
  for (const property of argument.properties) {
   if (property.type !== 'ObjectProperty' || property.computed) { fail('Apex parameters must be explicit named properties: '+method); continue; }
   const key=property.key.name || property.key.value;
   if (!expected.includes(key)) fail('Unknown Apex parameter '+key+' for '+method);
  }
 }
 const banned = new Set(['eval','Function','fetch','XMLHttpRequest','WebSocket','Worker','localStorage','sessionStorage','document','window','globalThis','navigator']);
 const blockedMembers = new Set(['innerHTML','outerHTML','insertAdjacentHTML','write','__proto__','constructor','prototype']);
 traverse(ast, {
  ImportDeclaration(p) {
   const module=p.node.source.value;
   for (const spec of p.node.specifiers) imports.set(spec.local.name,{module, imported:spec.imported?.name});
   if (module.startsWith('@salesforce/apex/')) {
    const method = module.slice('@salesforce/apex/'.length);
    if (p.node.specifiers.length !== 1 || p.node.specifiers[0].type !== 'ImportDefaultSpecifier') fail('Apex methods require a default import: '+method);
    if (!Object.prototype.hasOwnProperty.call(input.apexMethods || {}, method)) fail('Unverified Apex controller method: '+method);
   } else if (module === '@salesforce/apex') {
    if (p.node.specifiers.some(spec => spec.imported?.name !== 'refreshApex')) fail('Only refreshApex is supported from @salesforce/apex.');
   } else if (module.startsWith('@salesforce/schema/')) {
    const ref=module.slice(19).split('.');
    if (ref.length>2 || !input.objects[ref[0]] || (ref.length===2 && !input.objects[ref[0]].includes(ref[1]))) fail('Unknown schema import: '+module);
   } else if (!modules.has(module)) fail('Unsupported import: '+module+'. Use supported UI APIs or verified package-owned Apex methods. External modules are not supported.');
  },
  Decorator(p) {
   const n=p.node.expression;
   if(n.type==='CallExpression' && imports.get(n.callee.name)?.module === 'lwc' && imports.get(n.callee.name)?.imported === 'wire' && n.arguments[0]?.type==='Identifier') {
    const ref=imports.get(n.arguments[0].name);
    if(ref?.module.startsWith('@salesforce/apex/')) {
     const method=ref.module.slice('@salesforce/apex/'.length);
     if(!input.apexMethods?.[method]?.cacheable) fail('Wired Apex method must be cacheable: '+method);
     checkParameters(method,n.arguments[1]);
    }
   }
  },
  CallExpression(p) {
   if(p.node.callee.type !== 'Identifier') return;
   const ref=imports.get(p.node.callee.name);
   if(ref?.module.startsWith('@salesforce/apex/')) {
    checkParameters(ref.module.slice('@salesforce/apex/'.length),p.node.arguments[0]);
    let chain=p, handled=false;
    while(chain.parentPath?.isMemberExpression() && chain.parentPath.node.object===chain.node && chain.parentPath.parentPath?.isCallExpression()) {
     const member=chain.parentPath, call=member.parentPath;
     if(member.node.property.name==='catch' && call.node.arguments.length || member.node.property.name==='then' && call.node.arguments.length>1) handled=true;
     chain=call;
    }
    if(!handled) fail('Imperative Apex calls require an explicit rejection handler: '+ref.module);
   }
   if(ref && ((ref.module === 'lightning/uiRecordApi' && wireOnly.has(ref.imported)) || ['lightning/uiObjectInfoApi','lightning/uiRelatedListApi','lightning/uiListsApi'].includes(ref.module) && ref.imported?.startsWith('get'))) fail('UI API read adapters must be used with @wire: '+ref.imported);
  },
  StringLiteral(p) {
   const value=p.node.value;
   if(/^[A-Z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*$/.test(value)) {
    const [object,field]=value.split('.');
    if(!input.objects[object]?.includes(field)) fail('Unknown object.field literal: '+value);
   }
  },
  ExportDefaultDeclaration(p) {
   const node=p.node.declaration;
   const base=node.superClass?.name;
   if (node.type!=='ClassDeclaration' || !base || imports.get(base)?.module!=='lwc' || imports.get(base)?.imported!=='LightningElement') fail('Default class must extend the imported LightningElement.');
  },
  ReferencedIdentifier(p) { if (banned.has(p.node.name)) fail('Restricted global: '+p.node.name); },
  MemberExpression(p) {
   const n=p.node;
   if(n.computed && n.property.type!=='NumericLiteral') fail('Computed property access is outside the restricted source contract.');
   const name=n.computed ? n.property.value : n.property.name;
   if(blockedMembers.has(name)) fail('Restricted property: '+name);
   if(input.html.includes('lightning-record-picker') && name==='id' && n.object.type==='MemberExpression' && n.object.property.name==='detail') fail('Record picker handlers use detail.recordId, not detail.id.');
  },
  OptionalMemberExpression(p) {
   if(p.node.computed || blockedMembers.has(p.node.property.name)) fail('Restricted optional property access.');
  },
  Import(p) { fail('Dynamic imports are unsupported.'); },
  ImportExpression(p) { fail('Dynamic imports are unsupported.'); }
 });
 if(!ast.program.body.some(n=>n.type==='ExportDefaultDeclaration')) fail('Missing default component export.');
 if (/<\s*(script|iframe|object|embed|link)\b/i.test(input.html) || /\blwc:dom\s*=|\bon\w+\s*=\s*["']/i.test(input.html)) fail('Unsupported script, embedded content, manual DOM or inline event handler.');
 if(/\bobject-api-name\s*=\s*\{/.test(input.html)) fail('Use a literal verified object-api-name.');
 for (const m of input.html.matchAll(/\b(object-api-name|field-name)\s*=\s*["']([^"']+)["']/g)) {
  if(m[1]==='object-api-name' && !input.objects[m[2]]) fail('Unknown object-api-name: '+m[2]);
  if(m[1]==='field-name' && !Object.values(input.objects).some(fields=>fields.includes(m[2]))) fail('Unknown field-name: '+m[2]);
 }
 for(const m of input.html.matchAll(/\b(?:href|src)\s*=\s*(["'])(.*?)\1/g)) if(!/^[#\/]/.test(m[2]) || m[2].startsWith('//')) fail('External URL attributes are unsupported.');
 if(/\b(?:href|src)\s*=\s*\{/.test(input.html)) fail('Dynamic URL attributes require a separate reviewed contract.');
 for(const form of input.html.matchAll(/<lightning-record-(?:view|edit)-form\b([^>]*)>([\s\S]*?)<\/lightning-record-(?:view|edit)-form>/g)) {
  const obj=/object-api-name=["']([^"']+)["']/.exec(form[1])?.[1];
  if(!obj || !input.objects[obj]) { fail('Record forms require a literal verified object-api-name.'); continue; }
  for(const binding of form[2].matchAll(/field-name=\{([^}]+)\}/g)) {
   const module=imports.get(binding[1].trim())?.module;
   if(!module?.startsWith('@salesforce/schema/'+obj+'.')) fail('Field binding must reference a verified schema import for '+obj+'.');
  }
  for(const field of form[2].matchAll(/field-name=["']([^"']+)["']/g)) if(!input.objects[obj].includes(field[1])) fail('Field does not belong to record form object: '+obj+'.'+field[1]);
 }
 if (/@import|url\s*\(/i.test(input.css)) fail('External CSS resources are unsupported.');
 postcss.parse(input.css).walkRules(rule => {
  if (/\.slds-[A-Za-z0-9_-]+/.test(rule.selector)) fail('Do not redefine SLDS utility classes; use custom component CSS classes.');
 });
 const lint = new Linter();
 const messages=lint.verify(input.javascript,[{languageOptions:{parser:babelESLint,ecmaVersion:'latest',sourceType:'module',parserOptions:{requireConfigFile:false,babelOptions:{plugins:[[require.resolve('@babel/plugin-syntax-decorators'),{legacy:true}]]}}},plugins:{'@lwc/lwc':lwcPlugin,'@salesforce/lightning':lightningPlugin},rules:{'no-eval':'error','no-new-func':'error','@lwc/lwc/no-async-await':'error','@lwc/lwc/no-document-query':'error','@lwc/lwc/no-inner-html':'error','@lwc/lwc/no-api-reassignments':'error'}}]);
 for(const m of messages) if(m.severity===2) fail('Lint: '+m.message);
 for (const [ext,code] of [['js',input.javascript],['html',input.html],['css',input.css]]) {
  if(!code.trim()) continue;
  const result=transformSync(code,input.name+'.'+ext,{name:input.name,namespace:'c',apiVersion:Number(input.apiVersion)});
  for(const warning of result.warnings||[]) if(warning.level===1 || warning.level===2) fail('Compiler: '+warning.message);
 }
} catch(e) { fail(e.message); }
process.stdout.write(JSON.stringify({valid:errors.length===0,errors:[...new Set(errors)],checks:['Babel AST policy','Salesforce LWC compiler','Salesforce ESLint rules']}));
