import test from 'node:test';
import assert from 'node:assert/strict';
import { conversationRequirement, isStandaloneRequirement } from '../src/services/workspaceState.js';

test('clarification answers retain the original request and latest answer', () => {
  const value = conversationRequirement('Create Account', 'Reuse existing unchanged', { question: 'Already exists?' }, null);
  assert.match(value, /Create Account/);
  assert.match(value, /User answer: Reuse existing unchanged/);
});
test('draft follow-ups retain the requested behavior in a new draft', () => {
  const value = conversationRequirement('', 'Also add Status', null, { state: 'generated', requirement: 'Create Leave Request' });
  assert.match(value, /Create Leave Request/);
  assert.match(value, /Also add Status/);
  assert.match(value, /new reviewable draft/);
});
test('deployed requirements are reference context and only the new change is requested', () => {
  const value = conversationRequirement('', 'Add Status', null, { state: 'deployed', requirement: 'Create Leave Request' });
  assert.match(value, /context only; do not recreate/);
  assert.match(value, /Implement only this follow-up change/);
});
test('fresh message has no inherited requirements and input length is bounded', () => {
  assert.equal(conversationRequirement('old', ' New requirement ', null, null), 'New requirement');
  assert.throws(() => conversationRequirement('', ' ', null, null));
  assert.throws(() => conversationRequirement('', 'x'.repeat(40001), null, null));
});

test('reuse-only conversations keep the resolved org reference for follow-ups', () => {
  const value = conversationRequirement('Create Account\nUser answer: Reuse existing', 'Add a Status field', null, null, { continuing: true, referenceOnly: true });
  assert.match(value, /reference only; do not recreate/);
  assert.match(value, /Account/);
  assert.match(value, /Add a Status field/);
});

test('new named field request does not inherit a deployed field identity', () => {
  const text = 'Create a Text field on Account named Worker Resume Check,';
  const value = conversationRequirement('Create Worker Restart Check', text, null,
    { state: 'deployed', requirement: 'Create Worker_Restart_Check__c on Account' }, { continuing: true });
  assert.equal(value, text);
  assert.doesNotMatch(value, /Restart/);
});

test('complete new request replaces stale clarification but rename replies keep its parent', () => {
  const question = { question: 'Worker_Restart_Check__c exists. Reuse?' };
  const text = 'Create a Text field on Account named Worker Resume Check';
  assert.equal(conversationRequirement('Create Worker Restart Check', text, question, null), text);
  const answer = 'Create a separate field named Worker Resume Check';
  assert.equal(isStandaloneRequirement(answer), false);
  assert.match(conversationRequirement('Create field on Account', answer, question, null), /User answer:/);
});

test('new named objects, flows, Apex and LWC use current request only', () => {
  for (const text of ['Create an object named Resume Test', 'Create a Flow on Account named ResumeFlow',
    'Create an Apex class named ResumeController', 'Create a Lightning Web Component named resumeSearch']) {
    assert.equal(conversationRequirement('Old requirement', text, null, {state:'deployed', requirement:'Old requirement'}), text);
  }
  assert.equal(isStandaloneRequirement('Also create a field on Account named Extra'), false);
});
