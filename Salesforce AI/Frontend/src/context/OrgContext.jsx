import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../services/workspaceApi';
import { useAuth } from './AuthContext';

const OrgContext = createContext(null);
const storageKey = user => `metaflow.activeOrg.${user.id || user.email}`;
function savedOrg(user) {
  try { return localStorage.getItem(storageKey(user)) || ''; } catch { return ''; }
}
function remember(user, id) {
  try { localStorage.setItem(storageKey(user), id); } catch { /* Storage may be disabled. */ }
}
export default function OrgProvider({ children }) {
  const { user } = useAuth();
  const [organizations, setOrganizations] = useState([]);
  const [activeOrgId, setActiveOrgId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const generation = useRef(0);
  useEffect(() => {
    const current = ++generation.current;
    // Reset connection state when the authenticated account changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOrganizations([]); setActiveOrgId(''); setError(''); setLoading(Boolean(user));
    if (!user) return;
    apiRequest('default', '/orgs').then(rows => {
      if (generation.current !== current) return;
      const callbackId = new URLSearchParams(window.location.search).get('org');
      const preferred = callbackId || savedOrg(user);
      const id = rows.find(org => org.id === preferred)?.id || rows[0]?.id || '';
      setOrganizations(rows); setActiveOrgId(id); remember(user, id);
      if (id) {
        apiRequest('default', `/orgs/${encodeURIComponent(id)}/verify`, { method: 'POST' })
          .then(() => apiRequest('default', '/orgs'))
          .then(updated => { if (generation.current === current) setOrganizations(updated); })
          .catch(() => { /* Explicit connection checks expose transient failures in Settings. */ });
      }
      if (callbackId) {
        const url = new URL(window.location.href);
        url.searchParams.delete('org');
        window.history.replaceState(window.history.state, '', url);
      }
    }).catch(failure => {
      if (generation.current === current) setError(failure.message);
    }).finally(() => {
      if (generation.current === current) setLoading(false);
    });
    return () => { generation.current = current + 1; };
  }, [user]);
  function selectOrganization(id) {
    if (user && organizations.some(org => org.id === id)) {
      setActiveOrgId(id); remember(user, id);
    }
  }
  async function connect(environment, reconnectId = '') {
    setError('');
    try {
      const query = new URLSearchParams({ environment });
      if (reconnectId) query.set('reconnect_id', reconnectId);
      const data = await apiRequest('default', `/orgs/connect?${query}`, { method: 'POST' });
      window.location.assign(data.url);
    } catch (failure) { setError(failure.message); throw failure; }
  }
  async function verifyOrganization(id) {
    const current = generation.current;
    const result = await apiRequest('default', `/orgs/${encodeURIComponent(id)}/verify`, { method: 'POST' });
    const rows = await apiRequest('default', '/orgs');
    if (current === generation.current) setOrganizations(rows);
    return result;
  }
  async function removeOrganization(id) {
    const current = generation.current;
    const currentUser = user;
    await apiRequest('default', `/orgs/${encodeURIComponent(id)}`, { method: 'DELETE' });
    const rows = await apiRequest('default', '/orgs');
    if (current !== generation.current) return;
    setOrganizations(rows);
    setActiveOrgId(previous => {
      const next = rows.some(org => org.id === previous) ? previous : rows[0]?.id || '';
      if (currentUser) remember(currentUser, next);
      return next;
    });
  }
  const activeOrg = organizations.find(org => org.id === activeOrgId) || null;
  return <OrgContext.Provider value={{ organizations, activeOrg, activeOrgId, loading, error, connect, selectOrganization, verifyOrganization, removeOrganization }}>{children}</OrgContext.Provider>;
}
// eslint-disable-next-line react-refresh/only-export-components
export function useOrg() { return useContext(OrgContext); }
