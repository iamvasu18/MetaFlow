export function validTickets(value) {
  const rows = Array.isArray(value) ? value : value ? [value] : [];
  return rows.filter(row => row?.backgroundJob && typeof row.jobId === 'string' && typeof row.targetOrg === 'string' && typeof row.conversationId === 'string');
}
export function jobForChat(jobs, org, conversationId) {
  return jobs.find(job => job.targetOrg === org && job.conversationId === conversationId) || null;
}
export function addJob(jobs, ticket) {
  return [...jobs.filter(job => job.jobId !== ticket.jobId), ticket];
}
export function removeJob(jobs, id) {
  return jobs.filter(job => job.jobId !== id);
}
export function isOriginVisible(ticket, org, conversationId) {
  return ticket.targetOrg === org && ticket.conversationId === conversationId;
}
