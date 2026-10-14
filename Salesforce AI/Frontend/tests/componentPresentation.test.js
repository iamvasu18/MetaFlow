import test from 'node:test';
import assert from 'node:assert/strict';
import { componentErrors } from '../src/services/componentPresentation.js';

test('Permission Set deployment failures are attributed to their reviewed component', () => {
  const component = { metadataType: 'PermissionSet', fullName: 'Account_Access' };
  const bundle = { components: [component], lastResult: { result: { details: { componentFailures: [{ fileName: 'permissionsets/Account_Access.permissionset', problem: 'Missing required permission dependency' }] } } } };
  assert.deepEqual(componentErrors(bundle, component), ['Missing required permission dependency']);
});

import { packageErrors } from '../src/services/componentPresentation.js';

test('combined object XML failure appears once at package level when identity is unknown', () => {
  const components = [
    { metadataType:'CustomField', fullName:'Bank__c.Status__c' },
    { metadataType:'CustomField', fullName:'Bank__c.ClosedDate__c' },
    { metadataType:'ValidationRule', fullName:'Bank__c.RequireClosedDate' },
  ];
  const bundle = { components, lastResult: { result: { details: { componentFailures: { fileName:'objects/Bank__c.object', problem:'Picklist formula is invalid' } } } } };
  for (const component of components) assert.deepEqual(componentErrors(bundle, component), []);
  assert.equal(packageErrors(bundle).length, 1);
});

test('an exact rule identity wins over the combined object file path', () => {
  const object = {metadataType:'CustomObject', fullName:'Bank__c'};
  const field = {metadataType:'CustomField', fullName:'Bank__c.Status__c'};
  const rule = {metadataType:'ValidationRule', fullName:'Bank__c.RequireClosedDate'};
  const bundle = {components:[object,field,rule],lastResult:{result:{details:{componentFailures:[{fileName:'objects/Bank__c.object', fullName:rule.fullName, problem:'Use ISPICKVAL'}]}}}};
  assert.deepEqual(componentErrors(bundle, rule), ['Use ISPICKVAL']);
  assert.deepEqual(componentErrors(bundle, object), []);
  assert.deepEqual(componentErrors(bundle, field), []);
  assert.deepEqual(packageErrors(bundle), []);
});

test('local compiler checks are attributed only to their exact component', () => {
  const production={metadataType:'ApexClass',fullName:'Service'};
  const tests={metadataType:'ApexClass',fullName:'ServiceTest'};
  const bundle={localChecks:{errors:[{fullName:'ServiceTest',message:'ServiceTest: invalid Assert method'}]}};
  assert.deepEqual(componentErrors(bundle,production), []);
  assert.deepEqual(componentErrors(bundle,tests), ['ServiceTest: invalid Assert method']);
});
