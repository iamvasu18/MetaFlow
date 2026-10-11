import { apiRequest } from './workspaceApi.js';

export async function waitForBackgroundJob(ticket, { onProgress = () => {}, signal, request = apiRequest, delay = ms => new Promise(resolve => setTimeout(resolve, ms)) } = {}) {
  for (;;) {
    if (signal?.aborted) throw new Error('Background job tracking stopped. The saved job continues on the server.');
    let job;
    try {
      job = await request('default', `/jobs/${encodeURIComponent(ticket.jobId)}`);
    } catch (failure) {
      // Read-only tracking survives a web restart. Never repeat the POST that
      // created the job; Postgres remains the source of truth.
      if (failure.status && failure.status < 500) throw failure;
      onProgress({ ...ticket, state: 'reconnecting' });
      await delay(3000);
      continue;
    }
    if (signal?.aborted) throw new Error('Background job tracking stopped. The saved job continues on the server.');
    onProgress(job);
    if (job.state === 'succeeded') {
      if (!job.result?.planId) throw new Error('Completed job has no saved plan. Inspect the worker logs.');
      try {
        return await request('default', `/plans/${encodeURIComponent(job.result.planId)}`);
      } catch (failure) {
        if (failure.status && failure.status < 500) throw failure;
        onProgress({ ...ticket, state: 'reconnecting' });
        await delay(3000);
        continue;
      }
    }
    if (job.state === 'failed' || job.state === 'unknown') {
      const detail = job.result?.detail || 'Background job outcome needs attention.';
      const error = new Error(typeof detail === 'string' ? detail : detail.message || detail.question || JSON.stringify(detail));
      error.detail = detail;
      error.status = job.result?.status || 409;
      error.planId = job.result?.planId;
      throw error;
    }
    if (!['queued', 'running'].includes(job.state)) throw new Error('Unknown background job state.');
    await delay(2000);
  }
}
