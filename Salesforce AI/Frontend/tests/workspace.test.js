import test from 'node:test';
import assert from 'node:assert/strict';

import {
  canDeploy,
  canValidate,
  buildRequest,
  statusText,
} from '../src/services/workspaceState.js';

import { apiRequest } from '../src/services/workspaceApi.js';

const bundle = {
  id: 'saved',
  state: 'validated',
  sourceHash: 'exact-hash',
};

test('deployment requires validated state and approval of the exact source', () => {
  assert.equal(canDeploy(bundle, bundle.sourceHash), true);

  for (const state of [
    'generated',
    'failed',
    'pending',
    'running',
    'unknown',
    'deployed',
  ]) {
    assert.equal(
      canDeploy({ ...bundle, state }, bundle.sourceHash),
      false,
    );
  }

  assert.equal(canDeploy(bundle, 'previous-hash'), false);
  assert.equal(canDeploy(bundle, ''), false);
  assert.equal(canDeploy(null, ''), false);
});

test('running, pending, unknown and completed packages cannot be resubmitted', () => {
  for (const state of ['running', 'pending', 'unknown', 'deployed']) {
    assert.equal(canValidate({ ...bundle, state }), false);
  }

  for (const state of ['generated', 'failed', 'validated']) {
    assert.equal(canValidate({ ...bundle, state }), true);
  }
});

test('pure Apex request does not add LWC targets or permission sets', () => {
  assert.deepEqual(
    buildRequest('apex', {
      name: ' SearchService ',
      requirement: ' Search Contacts ',
      org: ' AIOrg ',
      objects: ' Contact, Account, ',
      targets: ['lightning__AppPage'],
    }),
    {
      class_name: 'SearchService',
      requirement: 'Search Contacts',
      target_org: 'AIOrg',
      objects: ['Contact', 'Account'],
    },
  );
});

test('LWC request includes the selected target', () => {
  const result = buildRequest('lwc', {
    name: 'contactSearch',
    requirement: 'Search',
    org: 'AIOrg',
    objects: '',
    targets: ['lightning__AppPage'],
  });

  assert.deepEqual(result.targets, ['lightning__AppPage']);
  assert.equal(result.component_name, 'contactSearch');
});

test('validation success is distinguished from deployment success', () => {
  assert.match(statusText(bundle), /No metadata was deployed/);
  assert.match(
    statusText({ state: 'deployed' }),
    /Deployment completed/,
  );
});

test('API sends exact approval hash to the scoped backend and never retries mutations', async t => {
  const calls = [];

  t.mock.method(globalThis, 'fetch', async (...args) => {
    calls.push(args);
    return new Response(JSON.stringify(bundle), { status: 200 });
  });

  await apiRequest('apex', '/bundles/saved/deploy', {
    method: 'POST',
    token: 'memory-only',
    body: {
      approved: true,
      source_hash: 'exact-hash',
    },
  });

  assert.equal(calls.length, 1);
  assert.equal(
    calls[0][0],
    '/api/apex/bundles/saved/deploy',
  );
  assert.equal(
    calls[0][1].headers.Authorization,
    'Bearer memory-only',
  );
  assert.deepEqual(
    JSON.parse(calls[0][1].body),
    {
      approved: true,
      source_hash: 'exact-hash',
    },
  );
});

test('API preserves backend validation failures', async t => {
  t.mock.method(
    globalThis,
    'fetch',
    async () => new Response(
      JSON.stringify({
        detail: 'Validation rule requires acceptance',
      }),
      { status: 422 },
    ),
  );

  await assert.rejects(
    apiRequest('apex', '/generate', {
      method: 'POST',
      body: {},
    }),
    /Validation rule requires acceptance/,
  );
});

test('HTML proxy errors are reported rather than treated as a package', async t => {
  t.mock.method(
    globalThis,
    'fetch',
    async () => new Response(
      '<html>Wrong server</html>',
      { status: 200 },
    ),
  );

  await assert.rejects(
    apiRequest('lwc', '/generate', {
      method: 'POST',
      body: {},
    }),
    /non-JSON.*proxy/,
  );
});

test('default request uses the existing general plan endpoint with no implementation selector', async t => {
  let call;

  t.mock.method(globalThis, 'fetch', async (...args) => {
    call = args;
    return new Response(JSON.stringify(bundle), { status: 200 });
  });

  await apiRequest('default', '/plan', {
    method: 'POST',
    body: {
      requirement: 'Show searchable contacts',
      target_org: 'AIOrg',
      generate_files: true,
    },
  });

  assert.equal(call[0], '/api/plan');

  assert.deepEqual(
    Object.keys(JSON.parse(call[1].body)).sort(),
    ['generate_files', 'requirement', 'target_org'],
  );
});

test('unified deployment requires saved approval and validation of the exact files', () => {
  const unified = {
    ...bundle,
    state: 'validated',
    plan: { summary: 'Search' },
    approvedHash: 'exact-hash',
    validatedHash: 'exact-hash',
  };

  assert.equal(canDeploy(unified, 'exact-hash'), true);

  assert.equal(
    canDeploy({ ...unified, approvedHash: undefined }, 'exact-hash'),
    false,
  );

  assert.equal(
    canDeploy({ ...unified, validatedHash: 'previous-hash' }, 'exact-hash'),
    false,
  );

  assert.equal(canDeploy(unified, 'previous-hash'), false);

  for (const state of [
    'generated',
    'queued',
    'running',
    'pending',
    'failed',
    'unknown',
    'deployed',
  ]) {
    assert.equal(
      canDeploy({ ...unified, state }, 'exact-hash'),
      false,
    );
  }
});
test('default approval uses the existing plan endpoint and exact source hash', async t => {
  let call;

  t.mock.method(globalThis, 'fetch', async (...args) => {
    call = args;
    return new Response(JSON.stringify(bundle), { status: 200 });
  });

  await apiRequest('default', '/plans/PLAN-1/approve', {
    method: 'POST',
    body: { source_hash: 'exact-hash' },
  });

  assert.equal(call[0], '/api/plans/PLAN-1/approve');

  assert.deepEqual(
    JSON.parse(call[1].body),
    { source_hash: 'exact-hash' },
  );
});

test('layout review uses the existing plan layout selection endpoint', async t => {
  let call;

  t.mock.method(globalThis, 'fetch', async (...args) => {
    call = args;
    return new Response('{}', { status: 200 });
  });

  const selection = {
    snapshotId: 'snapshot',
    selections: [
      {
        object: 'Contact',
        layouts: [
          {
            fullName: 'Contact-Contact Layout',
            sectionId: '0',
          },
        ],
      },
    ],
  };

  await apiRequest(
    'default',
    '/plans/PLAN-1/layout-selections',
    {
      method: 'POST',
      body: selection,
    },
  );

  assert.equal(
    call[0],
    '/api/plans/PLAN-1/layout-selections',
  );
  assert.deepEqual(
    JSON.parse(call[1].body),
    selection,
  );
});