import test from 'node:test';
import assert from 'node:assert/strict';
import { repairRequest, repairTarget } from '../src/services/repairRouting.js';
test('explicit corrections execute repair while issue questions remain explanations', () => {
  for (const value of ['fix it', 'can you resolve it?', 'please correct the error']) assert.equal(repairRequest(value), true);
  for (const value of ['what is the issue?', 'why did it fail?', 'create a field']) assert.equal(repairRequest(value), false);
});
test('multiple failing components require selection instead of an arbitrary repair', () => {
  const a={fullName:'One'}, b={fullName:'Two'};
  assert.equal(repairTarget({components:[a,b]}, () => ['error']), null);
  assert.equal(repairTarget({components:[a,b]}, c => c===b?['error']:[]), b);
});
