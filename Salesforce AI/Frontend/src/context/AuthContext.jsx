import { createContext, useContext, useEffect, useState } from 'react';
import { apiRequest } from '../services/workspaceApi';
const AuthContext = createContext(null);
export default function AuthProvider({ children }) {
  const [user, setUser] = useState(null); const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => { apiRequest('default', '/auth/me').then(setUser).catch(e => { if (e.status !== 401) setError(e.message); }).finally(() => setLoading(false)); }, []);
  async function signIn(mode, data) { setUser(await apiRequest('default', `/auth/${mode}`, {method:'POST', body:data})); }
  async function signOut() { await apiRequest('default','/auth/logout',{method:'POST'}); localStorage.removeItem('salesforce_plan_workspace_v2'); setUser(null); }
  return <AuthContext.Provider value={{user, loading, error, signIn, signOut}}>{children}</AuthContext.Provider>;
}
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() { return useContext(AuthContext); }
