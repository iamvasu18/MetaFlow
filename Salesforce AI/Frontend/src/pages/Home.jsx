import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Activity, ArrowRight, ArrowUpRight, Building2, Check, CheckCircle2,
  ChevronRight, Clock3, Cloud, Code2, FileText, GitBranch, LayoutDashboard,
  Plus, RefreshCw, Search, ShieldCheck, Sparkles, Upload, X, AlertCircle,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useOrg } from '../context/OrgContext';
import { apiRequest } from '../services/workspaceApi';
import { filterActivity, greeting, relativeTime } from '../services/homeState';
import './Home.css';

const starterPrompts = [
  { label: 'Create a custom object', icon: FileText, text: 'Create a custom object named Project to track project name, start date, end date, and status.' },
  { label: 'Build a Lightning component', icon: Code2, text: 'Build a Lightning Web Component that displays Account records in a searchable table.' },
  { label: 'Automate a business process', icon: GitBranch, text: 'Create a record-triggered flow that creates a follow-up Task when an Opportunity becomes Closed Won.' },
];
const activityIcons = {
  generated: Sparkles, approved: ShieldCheck, deployed: CheckCircle2,
  validated: Check, connected: Cloud, rejected: X, failed: AlertCircle,
  pending: Clock3, reviewed: FileText,
};
const activityNames = {
  generated: 'Generated', approved: 'Approved', deployed: 'Deployed',
  validated: 'Validated', connected: 'Connected', rejected: 'Rejected',
  failed: 'Needs attention', pending: 'Pending', reviewed: 'Reviewed',
};

function HeroArtwork() {
  return <div className="home-art" aria-hidden="true">
    <div className="home-art-cloud"><Cloud size={43} strokeWidth={1.6} /></div>
    <div className="home-art-line" />
    <div className="home-art-window">
      <div className="home-art-window-top"><span /><span /><span /><i /></div>
      <div className="home-art-caption">YOUR NEXT IDEA, CONNECTED</div>
      <div className="home-art-chart"><div className="home-art-bars">{[28, 45, 62, 40, 75].map((height, i) => <span key={i} style={{ height }} />)}</div><div className="home-art-ring"><Sparkles size={21} /></div></div>
      <div className="home-art-bottom"><span /><span /></div>
    </div>
    <div className="home-art-tag"><ShieldCheck size={16} /> Review. Approve. Deploy.</div>
    <div className="home-art-code"><Code2 size={22} /></div>
  </div>;
}

function ActivityRow({ item, onOpen, compact = false }) {
  const Icon = activityIcons[item.type] || Activity;
  const date = new Date(item.createdAt * 1000).toLocaleString();
  return <button className={`home-activity-row ${compact ? 'is-compact' : ''}`} onClick={() => onOpen(item)}>
    <span className={`home-event-icon event-${item.type}`}><Icon size={17} /></span>
    <span className="home-activity-copy"><strong>{item.title}</strong><span>{item.summary || (item.planId ? `Plan ${item.planId}` : 'Your Salesforce connection')}</span></span>
    {!compact && <span className={`home-event-state event-${item.type}`}>{activityNames[item.type] || item.type}</span>}
    <time dateTime={new Date(item.createdAt * 1000).toISOString()} title={date}>{relativeTime(item.createdAt)}</time>
    <ChevronRight size={14} className="home-event-arrow" />
  </button>;
}

export default function Home() {
  const { user } = useAuth();
  const { activeOrg, organizations, connect, loading: orgLoading, error: orgError, selectOrganization } = useOrg();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'activity' ? 'activity' : 'overview';
  const [resource, setResource] = useState(null);
  const [revision, setRevision] = useState(0);
  const [query, setQuery] = useState('');
  const [type, setType] = useState('all');
  const [environment, setEnvironment] = useState('production');
  const [connecting, setConnecting] = useState(false);
  const [connectionError, setConnectionError] = useState('');
  const dialog = useRef(null);
  const orgId = activeOrg?.id || '';
  const resourceKey = `${orgId}:${revision}`;
  const data = resource?.key === resourceKey ? resource.data : null;
  const error = resource?.key === resourceKey ? resource.error : '';
  const loading = orgLoading || resource?.key !== resourceKey;
  const firstName = user.name.trim().split(/\s+/)[0];

  useEffect(() => {
    if (orgLoading) return;
    let alive = true;
    const scope = orgId ? `&org_id=${encodeURIComponent(orgId)}` : '';
    apiRequest('default', `/home/overview?limit=100${scope}`)
      .then(result => { if (alive) setResource({key: resourceKey, data: result, error: ''}); })
      .catch(failure => { if (alive) setResource({key: resourceKey, data: null, error: failure.message}); });
    return () => { alive = false; };
  }, [orgId, orgLoading, resourceKey]);

  function selectTab(next) {
    setParams(next === 'activity' ? { tab: 'activity' } : {});
  }
  function openConnect() { setConnectionError(''); dialog.current?.showModal(); }
  function openWorkspace(requirement = '') {
    if (!activeOrg) { openConnect(); return; }
    navigate('/workspace', { state: { requirement } });
  }
  function openActivity(item) {
    if (!item.planId) { openConnect(); return; }
    if (item.orgId !== orgId) selectOrganization(item.orgId);
    navigate('/workspace', { state: { restorePlan: { kind: 'default', id: item.planId, targetOrg: item.orgId } } });
  }
  async function connectOrg(event) {
    event.preventDefault();
    if (connecting) return;
    setConnecting(true); setConnectionError('');
    try { await connect(environment); }
    catch (failure) { setConnectionError(failure.message); setConnecting(false); }
  }

  const stats = data?.stats;
  const activity = data?.activity || [];
  const filtered = filterActivity(activity, query, type);
  const connectionResult = params.get('connection');
  const statCards = [
    { label: 'Connected orgs', value: stats?.connectedOrgs, icon: Cloud, tone: 'blue', detail: 'Available to your account', filter: null },
    { label: 'Plans generated', value: stats?.plans, icon: FileText, tone: 'violet', detail: 'Your implementations', filter: 'generated' },
    { label: 'Plans approved', value: stats?.approved, icon: ShieldCheck, tone: 'amber', detail: 'Reviewed and approved', filter: 'approved' },
    { label: 'Plans deployed', value: stats?.deployed, icon: CheckCircle2, tone: 'green', detail: 'Confirmed by Salesforce', filter: 'deployed' },
  ];

  return <main className="apex-home">
    <section className="home-hero">
      <div className="home-hero-copy">
        <span className="home-eyebrow"><span className="home-mini-icon"><Sparkles size={15} /></span> SALESFORCE INTELLIGENCE PLATFORM</span>
        <h1>{greeting()}, {firstName}<span className="home-greeting-dot">.</span></h1>
        <p>Your ideas. Your org. One place to bring them together.<br className="home-desktop-break" /> Build, review, and deploy Salesforce changes with confidence.</p>
        <div className="home-hero-actions"><button className="home-button primary" onClick={() => openWorkspace()}><Sparkles size={16} /> Open AI workspace <ArrowRight size={15} /></button><button className="home-button secondary" onClick={() => { selectTab('overview'); document.getElementById('home-overview')?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }}>View overview <ArrowRight size={15} /></button></div>
        <span className="home-hero-note"><ShieldCheck size={13} /> You stay in control of every deployment.</span>
      </div>
      <HeroArtwork />
    </section>

    {connectionResult && <div className={`home-notice ${connectionResult === 'success' ? 'success' : ''}`} role="status"><CheckCircle2 size={17} /><span>{connectionResult === 'success' ? 'Salesforce authorization completed. Your connected org is ready below.' : 'Connection cancelled. You can connect an org whenever you’re ready.'}</span><button aria-label="Dismiss notification" onClick={() => { const next = new URLSearchParams(params); next.delete('connection'); next.delete('org'); setParams(next); }}><X size={16} /></button></div>}

    <section className="home-connection" aria-label="Salesforce connection">
      <div className="home-connection-main"><span className="home-connection-icon"><Building2 size={22} /></span><div><span className="home-section-kicker">{activeOrg ? 'SELECTED ENVIRONMENT' : 'YOUR SALESFORCE ENVIRONMENT'}</span><div className="home-connection-title"><h2>{orgLoading ? 'Checking your orgs…' : activeOrg?.name || 'Connect your first Salesforce org'}</h2>{activeOrg && <span className="home-connected"><span />{activeOrg.status || 'Not checked'}</span>}</div><p>{activeOrg ? `${activeOrg.type} · ${activeOrg.username}` : 'Authorize through Salesforce to unlock your AI workspace.'}</p></div></div>
      <div className="home-connection-actions">{activeOrg && <Link className="home-button secondary small" to="/settings">Manage connections</Link>}{activeOrg && <div className="home-connection-time"><Clock3 size={16} /><span>LAST WORKSPACE ACTIVITY<strong>{activity[0] ? relativeTime(activity[0].createdAt) : 'No activity yet'}</strong></span></div>}<button className="home-button secondary small" onClick={openConnect} disabled={orgLoading}><Plus size={15} />{activeOrg ? 'Connect another org' : 'Connect org'}</button></div>
    </section>
    {orgError && <p className="home-notice error" role="alert">{orgError}</p>}

    <div className="home-toolbar" id="home-overview"><div className="home-tabs" role="tablist" aria-label="Home sections"><button id="overview-tab" role="tab" aria-selected={tab === 'overview'} aria-controls="home-content" className={tab === 'overview' ? 'active' : ''} onClick={() => selectTab('overview')}><LayoutDashboard size={15} />Overview</button><button id="activity-tab" role="tab" aria-selected={tab === 'activity'} aria-controls="home-content" className={tab === 'activity' ? 'active' : ''} onClick={() => selectTab('activity')}><Activity size={15} />Recent activity{data?.activityTotal > 0 && <span>{data.activityTotal}</span>}</button></div><div className="home-toolbar-right"><span>{activeOrg ? 'Your work in this org' : 'Your account overview'}</span><button className="home-icon-button" aria-label="Refresh overview and activity" title="Refresh overview and activity" disabled={loading || orgLoading} onClick={() => setRevision(value => value + 1)}><RefreshCw size={16} className={loading ? 'home-spin' : ''} /></button></div></div>

    {error && <div className="home-notice error" role="alert"><AlertCircle size={18} /><span>Couldn’t load your overview. {error}</span><button onClick={() => setRevision(value => value + 1)}>Try again</button></div>}
    <div id="home-content" role="tabpanel" aria-labelledby={tab === 'overview' ? 'overview-tab' : 'activity-tab'}>
      {tab === 'overview' ? <>
        <div className="home-stats">{statCards.map(({ label, value, icon: Icon, tone, detail, filter }) => <button className="home-stat" key={label} onClick={() => { if (filter) { setType(filter); selectTab('activity'); } else openConnect(); }}><div className="home-stat-top"><span>{label}</span><span className={`home-stat-icon ${tone}`}><Icon size={17} /></span></div><strong className={loading ? 'home-stat-skeleton' : ''}>{loading ? '' : value ?? '—'}</strong><div className="home-stat-detail">{detail}<ArrowUpRight size={13} /></div></button>)}</div>
        <div className="home-main-grid">
          <section className="home-panel home-workflows"><div className="home-panel-heading"><div><h2>What would you like to do?</h2><p>A focused workspace for your next Salesforce change.</p></div><span className="home-section-tag">YOUR TOOLS</span></div>
            <div className="home-action-grid">
              <button className="home-action-card featured" onClick={() => openWorkspace()}><span className="home-action-symbol"><Sparkles size={23} /></span><ArrowUpRight size={17} className="home-card-arrow" /><h3>AI workspace</h3><p>Turn a requirement into a complete implementation. Review the files before you deploy.</p><span className="home-card-cta">Start building <ArrowRight size={14} /></span></button>
              <Link className="home-action-card" to="/import"><span className="home-action-symbol mint"><Upload size={22} /></span><ArrowUpRight size={17} className="home-card-arrow" /><h3>Import data <span className="home-preview-label">Preview</span></h3><p>Explore the existing import interface and field-mapping workflow.</p><span className="home-card-cta mint-text">Open import <ArrowRight size={14} /></span></Link>
              <Link className="home-action-card" to="/migration"><span className="home-action-symbol lavender"><GitBranch size={22} /></span><ArrowUpRight size={17} className="home-card-arrow" /><h3>Migrate org <span className="home-preview-label">Preview</span></h3><p>Explore the migration interface for moving metadata between environments.</p><span className="home-card-cta violet-text">Open migration <ArrowRight size={14} /></span></Link>
              <Link className="home-action-card" to="/dashboard/overview"><span className="home-action-symbol sky"><LayoutDashboard size={22} /></span><ArrowUpRight size={17} className="home-card-arrow" /><h3>Org intelligence <span className="home-preview-label">Live org data</span></h3><p>See Salesforce API usage, storage, licenses, users and metadata for your selected org.</p><span className="home-card-cta">Explore dashboard <ArrowRight size={14} /></span></Link>
            </div>
          </section>
          <section className="home-panel home-recent"><div className="home-panel-heading"><div><h2>Recent activity</h2><p>Real events from your workspace.</p></div><button className="home-text-button" onClick={() => { setType('all'); setQuery(''); selectTab('activity'); }}>View all <ArrowRight size={13} /></button></div>
            {loading ? <div className="home-activity-skeleton" aria-label="Loading activity">{[1, 2, 3, 4].map(value => <div key={value}><i /><span /></div>)}</div> : activity.length ? <div>{activity.slice(0, 5).map(item => <ActivityRow key={item.id} item={item} onOpen={openActivity} compact />)}</div> : <div className="home-empty"><span><Activity size={26} /></span><h3>Your story starts here</h3><p>{activeOrg ? 'Generate your first implementation. Its progress will appear here.' : 'Connect an org and start building. Your workspace activity will appear here.'}</p><button className="home-text-button" onClick={() => openWorkspace()}>{activeOrg ? 'Create your first plan' : 'Connect Salesforce'}<ArrowRight size={14} /></button></div>}
            {!!activity.length && <div className="home-recent-footer"><ShieldCheck size={14} /> Only your account’s workspace events appear here.</div>}
          </section>
        </div>
        <section className="home-starters"><div><span className="home-section-kicker">A LITTLE INSPIRATION</span><h2>Start with an idea.</h2></div><div className="home-starter-list">{starterPrompts.map(({ label, icon: Icon, text }) => <button key={label} onClick={() => openWorkspace(text)}><Icon size={17} /><span>{label}</span><ArrowUpRight size={14} /></button>)}</div></section>
      </> : <section className="home-panel home-activity-panel"><div className="home-panel-heading"><div><h2>Your workspace timeline</h2><p>Generation, review, validation, and deployment, in one place.</p></div><span className="home-section-tag">{data?.activityTotal ?? '—'} EVENTS</span></div><div className="home-activity-filters"><label className="home-search"><Search size={17} /><input aria-label="Search activity" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search activity or plan ID…" /></label><select aria-label="Filter activity type" value={type} onChange={event => setType(event.target.value)}><option value="all">All activity</option>{Object.entries(activityNames).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><button className="home-text-button" onClick={() => { setType('all'); setQuery(''); }} disabled={!query && type === 'all'}>Clear filters</button></div>{loading ? <div className="home-loading-line">Loading your activity…</div> : filtered.length ? filtered.map(item => <ActivityRow key={item.id} item={item} onOpen={openActivity} />) : <div className="home-empty"><span><Search size={25} /></span><h3>{activity.length ? 'No matching activity' : 'No activity yet'}</h3><p>{activity.length ? 'Try a different search or clear your filters.' : 'Your first workspace action will appear here.'}</p></div>}<div className="home-recent-footer">Showing {filtered.length} matches from the latest {activity.length} of {data?.activityTotal ?? 0} events. Plan links open the saved implementation in your workspace.</div></section>}
    </div>
    <footer className="home-page-footer"><span><Cloud size={13} />{activeOrg ? `Salesforce · ${activeOrg.status || 'Not checked'}` : 'Ready when you are'}</span><span>Describe <ChevronRight size={11} /> Review <ChevronRight size={11} /> Deploy</span></footer>

    <dialog className="home-connect-dialog" ref={dialog} aria-labelledby="connect-title"><form onSubmit={connectOrg}><button type="button" className="home-dialog-close" aria-label="Close connection dialog" disabled={connecting} onClick={() => dialog.current.close()}><X size={20} /></button><span className="home-dialog-cloud"><Cloud size={31} /></span><span className="home-section-kicker">YOUR ORG. YOUR WORKSPACE.</span><h2 id="connect-title">Connect Salesforce</h2><p>Choose your environment. You’ll securely sign in and authorize access on Salesforce’s own page.</p><label>Environment<select value={environment} disabled={connecting} onChange={event => setEnvironment(event.target.value)}><option value="production">Production / Developer org</option><option value="sandbox">Sandbox</option></select></label><div className="home-dialog-security"><ShieldCheck size={17} /><span>Your Salesforce password stays with Salesforce. Every deployment still requires your approval.</span></div>{(connectionError || orgError) && <p role="alert" className="home-dialog-error">{connectionError || orgError}</p>}<button className="home-button primary" disabled={connecting}>{connecting ? 'Opening Salesforce…' : 'Continue to Salesforce'}<ArrowRight size={16} /></button>{organizations.length > 0 && <small>{organizations.length} org{organizations.length === 1 ? '' : 's'} already connected to your account.</small>}</form></dialog>
  </main>;
}
