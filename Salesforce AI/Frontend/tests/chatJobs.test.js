import test from 'node:test';
import assert from 'node:assert/strict';
import { validTickets, addJob, removeJob, jobForChat, isOriginVisible } from '../src/services/chatJobs.js';
const a = { backgroundJob: true, jobId: 'a', targetOrg: 'org', conversationId: 'chat-a' };
const b = { ...a, jobId: 'b', conversationId: 'chat-b' };
test('multiple chats retain independent pending jobs and completing A preserves B', () => {
  const jobs = addJob(addJob([], a), b);
  assert.equal(jobForChat(jobs, 'org', 'chat-a'), a);
  assert.equal(jobForChat(jobs, 'org', 'chat-b'), b);
  assert.equal(jobForChat(jobs, 'org', null), null);
  assert.deepEqual(removeJob(jobs, 'a'), [b]);
});
test('completion and progress may affect only the originating chat and org', () => {
  assert.equal(isOriginVisible(a, 'org', 'chat-a'), true);
  assert.equal(isOriginVisible(a, 'org', 'chat-b'), false);
  assert.equal(isOriginVisible(a, 'other-org', 'chat-a'), false);
});
test('refresh recovery preserves all jobs and migrates the previous single ticket', () => {
  assert.deepEqual(validTickets(JSON.parse(JSON.stringify([a, b]))), [a, b]);
  assert.deepEqual(validTickets(a), [a]);
  assert.deepEqual(validTickets([{}, { ...a, conversationId: null }]), []);
});
test('ticket replacement is idempotent and does not discard another chat', () => {
  assert.deepEqual(addJob([a, b], { ...a, state: 'running' }), [b, { ...a, state: 'running' }]);
});

import { sameOperation } from '../src/services/chatJobs.js';

test('a delayed status completion cannot overwrite another chat, source revision or deployment job', async () => {
  const origin = {chat:'A',org:'org',id:'plan',sourceHash:'old',jobId:'validation'};
  let current = {...origin};
  let resolve;
  const pending = new Promise(done => { resolve=done; });
  let result;
  const track = pending.then(value => { if (sameOperation(origin,current)) result=value; });
  current = {...origin,chat:'B'};
  resolve('old failure');
  await track;
  assert.equal(result, undefined);
  for (const change of [{sourceHash:'new'},{jobId:'deploy'},{id:'other'},{org:'other'}]) {
    assert.equal(sameOperation(origin,{...origin,...change}), false);
  }
  assert.equal(sameOperation(origin,{...origin}), true);
});
