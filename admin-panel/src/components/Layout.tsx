import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { api, type ModelDef } from '../api';
import { useAuth } from '../auth';

function sectionIcon(app: string): string {
  const icons: Record<string, string> = {
    accounts: '👤', affiliate: '🔗', autotopup: '🔁', bonus: '🎁',
    broadcast: '📣', group_payment: '👥', loyalty_market: '⭐',
    market_place: '🎟', notifications: '🔔', payments: '💳',
    support: '🛟', transactions: '💸', user_preference: '⚙', wallet: '👛',
  };
  return icons[app] || '📦';
}

export default function Layout() {
  const { logout } = useAuth();
  const location = useLocation();
  const [models, setModels] = useState<ModelDef[] | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    let live = true;
    Promise.all([api.models(), api.dashboard()])
      .then(([m, d]) => {
        if (!live) return;
        setModels(m);
        const c: Record<string, number> = {};
        for (const row of d) c[row.model] = row.count;
        setCounts(c);
      })
      .catch(() => {});
    return () => { live = false; };
  }, [location.pathname === '/']);

  const groups: Record<string, ModelDef[]> = {};
  for (const m of models || []) {
    const app = m.name.split('.')[0];
    (groups[app] ||= []).push(m);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/" className="sidebar-brand">BlueSea Admin</Link>
        <nav>
          <div className="sidebar-group">
            <NavLink to="/" end className={({ isActive }) => isActive ? 'sidebar-link active' : 'sidebar-link'}>
              📊 <span className="lbl">Dashboard</span>
            </NavLink>
          </div>
          {Object.entries(groups).map(([app, ms]) => (
            <div className="sidebar-group" key={app}>
              <div className="sidebar-group-title">{sectionIcon(app)} {app.replace(/_/g, ' ')}</div>
              {ms.map((m) => (
                <NavLink
                  key={m.name}
                  to={`/models/${encodeURIComponent(m.name)}`}
                  className={({ isActive }) => isActive ? 'sidebar-link active' : 'sidebar-link'}
                  title={m.label}
                >
                  <span className="lbl">{m.label}</span>
                  <span className="count">{counts[m.name] ?? ''}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <button className="btn" style={{ width: '100%' }} onClick={logout}>Logout</button>
        </div>
      </aside>
      <div className="main">
        <div className="content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
