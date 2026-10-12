import test from 'node:test';
import assert from 'node:assert/strict';
import {componentErrors} from '../src/services/componentPresentation.js';

test('coverage failure is shown on its production class', () => {
  const bundle = {lastResult: {result: {details: {runTestResult: {
    codeCoverageWarnings: [{name: 'AccountService', message: 'Coverage is 50%; 75% required'}],
  }}}}};
  assert.match(componentErrors(bundle, {metadataType: 'ApexClass', fullName: 'AccountService'})[0], /50%/);
  assert.deepEqual(componentErrors(bundle, {metadataType: 'ApexClass', fullName: 'Other'}), []);
});

test('test failure and stack trace belong to the test class', () => {
  const bundle = {lastResult: {result: {details: {runTestResult: {
    failures: [{name: 'AccountServiceTest', methodName: 'testEmpty', message: 'Assertion failed', stackTrace: 'line 12'}],
  }}}}};
  const errors = componentErrors(bundle, {metadataType: 'ApexClass', fullName: 'AccountServiceTest'});
  assert.match(errors[0], /testEmpty/);
  assert.match(errors[0], /line 12/);
});

test('singleton compiler failure retains its line and strips Salesforce HTML', () => {
  const bundle = {lastResult: {result: {details: {componentFailures: {
    fileName: 'classes/AccountService.cls', problem: '<a>Invalid method</a>', lineNumber: 8,
  }}}}};
  assert.deepEqual(componentErrors(bundle, {metadataType: 'ApexClass', fullName: 'AccountService'}), ['Line 8: Invalid method']);
});
