import test from 'node:test';
import assert from 'node:assert/strict';
import { waitForBackgroundJob } from '../src/services/backgroundJobs.js';

test('queued and running jobs resolve through the saved owned plan', async () => {
  const states=['queued','running','succeeded']; const progress=[]; const paths=[];
  const result=await waitForBackgroundJob({jobId:'JOB-test'}, {delay:async()=>{},onProgress:job=>progress.push(job.state),request:async(kind,path)=>{
    paths.push(path);
    return path.startsWith('/jobs/') ? {state:states.shift(),result:{planId:'PLAN-test'}} : {id:'PLAN-test'};
  }});
  assert.deepEqual(progress,['queued','running','succeeded']);
  assert.equal(paths.at(-1),'/plans/PLAN-test'); assert.equal(result.id,'PLAN-test');
});
test('clarification and repair evidence survives background errors', async () => {
  const detail={code:'CLARIFICATION_REQUIRED',question:'Reuse Account?'};
  await assert.rejects(waitForBackgroundJob({jobId:'JOB-test'}, {request:async()=>({state:'failed',result:{detail,status:422}})}),error=>error.detail===detail&&error.status===422);
});
test('aborted browser tracking makes no request and does not cancel server work', async () => {
  const controller=new AbortController();controller.abort();let calls=0;
  await assert.rejects(waitForBackgroundJob({jobId:'JOB-test'}, {signal:controller.signal,request:async()=>{calls++;}}),/continues on the server/);
  assert.equal(calls,0);
});

test('web outage retries only status reads and resumes without repeating generation', async () => {
  let attempts=0;const paths=[];const progress=[];
  const result=await waitForBackgroundJob({jobId:'JOB-existing'}, {delay:async()=>{},onProgress:value=>progress.push(value.state),request:async(kind,path)=>{
    paths.push(path);
    if (path.startsWith('/jobs/')) { if (attempts++===0) throw new Error('Web server unavailable'); return {state:'succeeded',result:{planId:'PLAN-existing'}}; }
    return {id:'PLAN-existing'};
  }});
  assert.equal(result.id,'PLAN-existing');assert.equal(progress[0],'reconnecting');
  assert.deepEqual(paths,['/jobs/JOB-existing','/jobs/JOB-existing','/plans/PLAN-existing']);
});
