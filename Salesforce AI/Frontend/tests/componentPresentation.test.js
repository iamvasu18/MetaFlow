import test from 'node:test';
import assert from 'node:assert/strict';
import { componentErrors } from '../src/services/componentPresentation.js';

test('Permission Set deployment failures are attributed to their reviewed component', () => {
  const component = { metadataType: 'PermissionSet', fullName: 'Account_Access' };
  const bundle = { components: [component], lastResult: { result: { details: { componentFailures: [{ fileName: 'permissionsets/Account_Access.permissionset', problem: 'Missing required permission dependency' }] } } } };
  assert.deepEqual(componentErrors(bundle, component), ['Missing required permission dependency']);
});
