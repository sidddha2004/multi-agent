import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import './App.css';

const API = (process.env.REACT_APP_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const AGENTS = {
  research: { label: 'Research', glyph: '◎', hue: 'var(--c-research)' },
  analysis: { label: 'Analysis', glyph: '△', hue: 'var(--c-analysis)' },
  writing: { label: 'Writing', glyph: '✎', hue: 'var(--c-writing)' },
};
const agentOf = (t) => AGENTS[t] || { label: t || 'Agent', glyph: '◇', hue: 'var(--c-research)' };

const EXAMPLES = [
  'Compare PostgreSQL and MongoDB for a fintech startup',
  'Draft a launch announcement for an AI security product',
  'Analyse the pros and cons of microservices vs a monolith',
  'Explain zero-trust architecture and give a rollout checklist',
];

const STAGES = [
  { key: 'plan', label: 'Planner', hint: 'Splitting request into subtasks' },
  { key: 'agents', label: 'Agents', hint: 'Specialists working in sequence' },
  { key: 'merge', label: 'Aggregator', hint: 'Merging outputs into one answer' },
  { key: 'done', label: 'Delivered', hint: 'Stored in your history' },
];

/* ---------- tiny safe markdown renderer (React elements only, no innerHTML) ---------- */
function inline(text, keyBase) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith('**')) out.push(<strong key={`${keyBase}-${i++}`}>{tok.slice(2, -2)}</strong>);
    else out.push(<code key={`${keyBase}-${i++}`}>{tok.slice(1, -1)}</code>);
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const LIST_RE = /^\s*([-*•]|\d+\.)\s/;

function Markdown({ text }) {
  const blocks = [];
  const lines = String(text || '').split('\n');
  let i = 0;
  let k = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim().startsWith('```')) {
      const buf = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) buf.push(lines[i++]);
      i++;
      blocks.push(<pre key={k++}><code>{buf.join('\n')}</code></pre>);
    } else if (/^#{1,4}\s/.test(line)) {
      const lvl = Math.min(line.match(/^#+/)[0].length + 2, 6);
      const Tag = `h${lvl}`;
      blocks.push(<Tag key={k++}>{inline(line.replace(/^#+\s/, ''), k)}</Tag>);
      i++;
    } else if (LIST_RE.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items = [];
      while (i < lines.length && LIST_RE.test(lines[i])) {
        items.push(lines[i].replace(LIST_RE, ''));
        i++;
      }
      const L = ordered ? 'ol' : 'ul';
      blocks.push(<L key={k++}>{items.map((it, j) => <li key={j}>{inline(it, `${k}-${j}`)}</li>)}</L>);
    } else if (line.trim() === '') {
      i++;
    } else {
      const buf = [];
      while (i < lines.length && lines[i].trim() !== '' && !/^(#{1,4}\s|```)/.test(lines[i]) && !LIST_RE.test(lines[i])) buf.push(lines[i++]);
      blocks.push(<p key={k++}>{inline(buf.join(' '), k)}</p>);
    }
  }
  return <div className="md">{blocks}</div>;
}

/* ---------- helpers ---------- */
function timeAgo(ts) {
  if (!ts) return '';
  const s = Math.max(0, Math.floor((Date.now() - new Date(ts).getTime()) / 1000));
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function download(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function jobToMarkdown(job) {
  const parts = [`# ${job.prompt}`, '', `Trace: ${job.trace_id}  `, `Status: ${job.status}`, ''];
  if (job.summary) parts.push('## Final answer', '', job.summary, '');
  (job.tasks || []).forEach((t, i) => {
    parts.push(`## Task ${i + 1} · ${agentOf(t.agent_type).label}`, '', `*${t.description}*`, '', t.result || '', '');
  });
  return parts.join('\n');
}

/* ---------- components ---------- */
function NetworkArt() {
  const links = [[200, 150, 80, 60], [200, 150, 320, 70], [200, 150, 90, 240], [200, 150, 310, 235], [80, 60, 320, 70], [90, 240, 310, 235], [80, 60, 90, 240], [320, 70, 310, 235]];
  const nodes = [[80, 60, '◎'], [320, 70, '△'], [90, 240, '✎'], [310, 235, '⛨']];
  return (
    <svg className="net" viewBox="0 0 400 300" aria-hidden="true">
      <defs>
        <radialGradient id="glow"><stop offset="0%" stopColor="var(--accent)" stopOpacity=".9" /><stop offset="100%" stopColor="var(--accent)" stopOpacity="0" /></radialGradient>
      </defs>
      {links.map((l, i) => (
        <line key={i} x1={l[0]} y1={l[1]} x2={l[2]} y2={l[3]} className="net-line" style={{ animationDelay: `${i * 0.3}s` }} />
      ))}
      <circle cx="200" cy="150" r="46" fill="url(#glow)" className="net-pulse" />
      <circle cx="200" cy="150" r="12" className="net-core" />
      {nodes.map((n, i) => (
        <g key={i} className="net-node" style={{ animationDelay: `${i * 0.5}s` }}>
          <circle cx={n[0]} cy={n[1]} r="22" />
          <text x={n[0]} y={n[1] + 6} textAnchor="middle">{n[2]}</text>
        </g>
      ))}
    </svg>
  );
}

function AuthScreen({ onAuthed, toast, theme, toggleTheme }) {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      if (mode === 'register') {
        const r = await fetch(`${API}/auth/register`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password, name: name || email.split('@')[0] }),
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'Could not create account (check email and 8+ char password)');
        toast('Account created. Signing you in…', 'ok');
      }
      const r = await fetch(`${API}/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'Login failed');
      onAuthed(d.access_token, email);
    } catch (err) {
      setError(err.message === 'Failed to fetch' ? 'Network error. Is the API reachable?' : err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <section className="auth-hero">
        <div className="brand"><span className="brand-mark">⛨</span> SecureAI</div>
        <NetworkArt />
        <h1>One prompt.<br />A team of AI agents.</h1>
        <p className="lede">Planner, specialist agents and an aggregator turn a single request into a verified, stored answer, powered by Gemini 2.5 Flash.</p>
        <ul className="feature-list">
          <li><b>Planner</b> splits work into focused subtasks</li>
          <li><b>Specialists</b> for research, analysis and writing</li>
          <li><b>Aggregator</b> merges everything into one answer</li>
          <li><b>Private history</b> with export and full traceability</li>
        </ul>
      </section>
      <section className="auth-panel">
        <button className="ghost icon-btn theme-fab" onClick={toggleTheme} aria-label="Toggle theme">{theme === 'dark' ? '☀' : '☾'}</button>
        <form className="auth-card" onSubmit={submit}>
          <h2>{mode === 'login' ? 'Welcome back' : 'Create your workspace'}</h2>
          <p className="muted">{mode === 'login' ? 'Sign in to your mission control.' : 'Free to use. No card required.'}</p>
          {mode === 'register' && (
            <label>Name<input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ada Lovelace" maxLength={100} /></label>
          )}
          <label>Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" autoComplete="email" /></label>
          <label>Password<input type="password" required minLength={8} maxLength={72} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></label>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button className="primary wide" disabled={busy}>{busy ? 'Working…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
          <p className="switch">
            {mode === 'login' ? 'New here?' : 'Already registered?'}{' '}
            <button type="button" className="link" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}>
              {mode === 'login' ? 'Create an account' : 'Sign in'}
            </button>
          </p>
        </form>
      </section>
    </div>
  );
}

function Pipeline({ stage }) {
  return (
    <ol className="pipeline" aria-live="polite">
      {STAGES.map((s, i) => {
        const state = i < stage ? 'done' : i === stage ? 'active' : 'idle';
        return (
          <li key={s.key} className={`pstep ${state}`}>
            <span className="pdot">{state === 'done' ? '✓' : i + 1}</span>
            <span className="ptext"><b>{s.label}</b><small>{s.hint}</small></span>
          </li>
        );
      })}
    </ol>
  );
}

function Drawer({ job, onClose, onDelete, toast }) {
  useEffect(() => {
    const h = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);
  if (!job) return null;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(job.summary || (job.tasks || []).map((t) => t.result).join('\n\n'));
      toast('Copied to clipboard', 'ok');
    } catch {
      toast('Copy failed', 'err');
    }
  };
  const tasks = job.tasks || [];
  return (
    <div className="drawer-wrap" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Job result">
        <header>
          <div>
            <span className={`badge ${job.status}`}>{job.status}</span>
            <h3>{job.prompt}</h3>
            <small className="mono muted">trace {job.trace_id}</small>
          </div>
          <button className="ghost icon-btn" onClick={onClose} aria-label="Close">✕</button>
        </header>
        <div className="drawer-actions">
          <button className="ghost" onClick={copy}>Copy answer</button>
          <button className="ghost" onClick={() => download(`secureai-job-${job.job_id}.md`, jobToMarkdown(job))}>Export .md</button>
          <button className="ghost danger" onClick={() => onDelete(job.job_id)}>Delete</button>
        </div>
        <div className="drawer-body">
          {job.summary && (
            <section className="answer">
              <h4>Final answer</h4>
              <Markdown text={job.summary} />
            </section>
          )}
          <h4 className="sect">Agent trace · {tasks.length} task{tasks.length === 1 ? '' : 's'}</h4>
          {tasks.map((t, i) => {
            const a = agentOf(t.agent_type);
            return (
              <article className="trace" key={t.task_id} style={{ '--hue': a.hue }}>
                <div className="trace-head">
                  <span className="agent-chip"><span>{a.glyph}</span>{a.label} agent</span>
                  <span className={`badge ${t.status}`}>{t.status}</span>
                </div>
                <p className="trace-desc">{i + 1}. {t.description}</p>
                <Markdown text={t.result} />
              </article>
            );
          })}
        </div>
      </aside>
    </div>
  );
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('token'));
  const [email, setEmail] = useState(() => localStorage.getItem('email') || '');
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');
  const [jobs, setJobs] = useState([]);
  const [prompt, setPrompt] = useState('');
  const [stage, setStage] = useState(-1);
  const [running, setRunning] = useState(false);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [detail, setDetail] = useState(null);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [toasts, setToasts] = useState([]);
  const timers = useRef([]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toast = useCallback((text, kind = 'ok') => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, text, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);

  const logout = useCallback((msg) => {
    localStorage.removeItem('token');
    setToken(null);
    setJobs([]);
    setDetail(null);
    if (msg) toast(msg, 'err');
  }, [toast]);

  const api = useCallback(async (path, opts = {}) => {
    const r = await fetch(`${API}${path}`, {
      ...opts,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}`, ...(opts.headers || {}) },
    });
    if (r.status === 401) {
      logout('Session expired. Please sign in again.');
      throw new Error('unauthorized');
    }
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${r.status})`);
    return data;
  }, [token, logout]);

  const loadJobs = useCallback(async () => {
    setLoadingJobs(true);
    try {
      const d = await api('/api/jobs?limit=100');
      setJobs(d.jobs || []);
    } catch (e) {
      if (e.message !== 'unauthorized') toast('Could not load history', 'err');
    } finally {
      setLoadingJobs(false);
    }
  }, [api, toast]);

  useEffect(() => { if (token) loadJobs(); }, [token, loadJobs]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const onAuthed = (tok, mail) => {
    localStorage.setItem('token', tok);
    localStorage.setItem('email', mail);
    setToken(tok);
    setEmail(mail);
    toast('Signed in', 'ok');
  };

  const run = async (e) => {
    if (e) e.preventDefault();
    const text = prompt.trim();
    if (!text || running) return;
    setRunning(true);
    setStage(0);
    timers.current.forEach(clearTimeout);
    timers.current = [setTimeout(() => setStage(1), 2200), setTimeout(() => setStage(2), 9000)];
    try {
      const res = await api('/api/jobs', { method: 'POST', body: JSON.stringify({ prompt: text }) });
      timers.current.forEach(clearTimeout);
      setStage(3);
      setPrompt('');
      await loadJobs();
      const full = await api(`/api/jobs/${res.job_id}`);
      setDetail(full);
      toast(res.status === 'completed' ? 'Mission complete' : 'Finished with errors', res.status === 'completed' ? 'ok' : 'err');
    } catch (err) {
      timers.current.forEach(clearTimeout);
      setStage(-1);
      if (err.message !== 'unauthorized') toast(err.message === 'Failed to fetch' ? 'Network error' : err.message, 'err');
    } finally {
      setRunning(false);
      setTimeout(() => setStage(-1), 2500);
    }
  };

  const openJob = async (id) => {
    try {
      setDetail(await api(`/api/jobs/${id}`));
    } catch (e) {
      if (e.message !== 'unauthorized') toast('Could not open job', 'err');
    }
  };

  const deleteJob = async (id) => {
    if (!window.confirm('Delete this job and its results permanently?')) return;
    try {
      await api(`/api/jobs/${id}`, { method: 'DELETE' });
      setDetail(null);
      setJobs((j) => j.filter((x) => x.job_id !== id));
      toast('Job deleted', 'ok');
    } catch (e) {
      if (e.message !== 'unauthorized') toast(e.message, 'err');
    }
  };

  const stats = useMemo(() => {
    const done = jobs.filter((j) => j.status === 'completed').length;
    const failed = jobs.filter((j) => j.status === 'failed').length;
    const today = jobs.filter((j) => Date.now() - new Date(j.created_at).getTime() < 86400000).length;
    return { total: jobs.length, done, failed, today, rate: jobs.length ? Math.round((done / jobs.length) * 100) : 0 };
  }, [jobs]);

  const shown = jobs.filter((j) => (filter === 'all' || j.status === filter) && j.prompt.toLowerCase().includes(query.toLowerCase()));
  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'));

  const toastEls = (
    <div className="toasts" role="status">
      {toasts.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.text}</div>)}
    </div>
  );

  if (!token) {
    return (
      <>
        <AuthScreen onAuthed={onAuthed} toast={toast} theme={theme} toggleTheme={toggleTheme} />
        {toastEls}
      </>
    );
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">⛨</span> SecureAI <span className="env">Mission Control</span></div>
        <div className="top-actions">
          <span className="live"><i /> Gemini 2.5 Flash</span>
          <button className="ghost icon-btn" onClick={toggleTheme} aria-label="Toggle theme">{theme === 'dark' ? '☀' : '☾'}</button>
          <span className="user-chip" title={email}>{(email || '?')[0].toUpperCase()}</span>
          <button className="ghost" onClick={() => logout()}>Sign out</button>
        </div>
      </header>

      <main className="content">
        <section className="stats">
          <div className="stat"><small>Total missions</small><b>{stats.total}</b></div>
          <div className="stat"><small>Last 24h</small><b>{stats.today}</b></div>
          <div className="stat">
            <small>Success rate</small><b>{stats.rate}<em>%</em></b>
            <div className="bar"><span style={{ width: `${stats.rate}%` }} /></div>
          </div>
          <div className="stat"><small>Failed</small><b className={stats.failed ? 'bad' : ''}>{stats.failed}</b></div>
        </section>

        <section className="composer card">
          <div className="card-head">
            <h2>New mission</h2>
            <span className="muted hint-kbd"><kbd>Ctrl</kbd>+<kbd>Enter</kbd> to launch</span>
          </div>
          <form onSubmit={run}>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') run(e); }}
              placeholder="Describe what you want the agents to accomplish…"
              maxLength={5000}
              rows={4}
              disabled={running}
            />
            <div className="composer-foot">
              <div className="chips">
                {EXAMPLES.map((x) => <button type="button" key={x} className="chip" disabled={running} onClick={() => setPrompt(x)}>{x}</button>)}
              </div>
              <div className="launch">
                <small className="muted">{prompt.length}/5000</small>
                <button className="primary" disabled={running || !prompt.trim()}>{running ? 'Agents working…' : 'Launch agents →'}</button>
              </div>
            </div>
          </form>
          {stage >= 0 && <Pipeline stage={stage} />}
        </section>

        <section className="history card">
          <div className="card-head">
            <h2>Mission history</h2>
            <div className="tools">
              <input className="search" placeholder="Search prompts…" value={query} onChange={(e) => setQuery(e.target.value)} />
              <div className="seg">
                {['all', 'completed', 'failed'].map((f) => (
                  <button key={f} className={filter === f ? 'on' : ''} onClick={() => setFilter(f)}>{f}</button>
                ))}
              </div>
              <button className="ghost" onClick={loadJobs} disabled={loadingJobs} aria-label="Refresh">{loadingJobs ? '…' : '↻'}</button>
            </div>
          </div>
          {shown.length === 0 ? (
            <div className="empty">
              <div className="empty-art">⛨</div>
              <p>{jobs.length === 0 ? 'No missions yet. Launch your first one above.' : 'No missions match your filters.'}</p>
            </div>
          ) : (
            <ul className="jobs">
              {shown.map((j) => (
                <li key={j.job_id}>
                  <button className="job" onClick={() => openJob(j.job_id)}>
                    <span className={`dot ${j.status}`} />
                    <span className="job-main">
                      <span className="job-prompt">{j.prompt}</span>
                      <small className="mono muted">#{j.job_id} · {timeAgo(j.created_at)}</small>
                    </span>
                    <span className={`badge ${j.status}`}>{j.status}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
      <Drawer job={detail} onClose={() => setDetail(null)} onDelete={deleteJob} toast={toast} />
      {toastEls}
    </div>
  );
}

export default App;
