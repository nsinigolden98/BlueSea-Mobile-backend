import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, api, type CashflowResp, type ModelDef } from '../api';
import { ErrorBox, Spinner, formatMoney } from '../components/ui';

function CashflowChart({ data }: { data: CashflowResp }) {
  const W = 900, H = 240, PAD_L = 8, PAD_B = 22, PAD_T = 8;
  const max = Math.max(1, ...data.series.map((p) => Math.max(p.inflow, p.outflow)));
  const n = data.series.length;
  const slot = (W - PAD_L) / n;
  const barW = Math.max(2, Math.min(14, slot / 2 - 3));
  const y = (v: number) => PAD_T + (H - PAD_T - PAD_B) * (1 - v / max);
  const labelEvery = Math.max(1, Math.ceil(n / 10));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', display: 'block' }} role="img" aria-label="Cash inflow vs outflow">
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <g key={f}>
          <line x1={PAD_L} x2={W} y1={y(max * f)} y2={y(max * f)} stroke="#e5e7eb" strokeWidth={1} />
          <text x={W - 2} y={y(max * f) - 3} fontSize={9} fill="#9ca3af" textAnchor="end">
            {formatMoney(max * f)}
          </text>
        </g>
      ))}
      {data.series.map((p, i) => {
        const cx = PAD_L + slot * i + slot / 2;
        return (
          <g key={p.date}>
            <title>{`${p.date}: in ${formatMoney(p.inflow)}, out ${formatMoney(p.outflow)}`}</title>
            <rect x={cx - barW - 1} y={y(p.inflow)} width={barW} height={H - PAD_B - y(p.inflow)} fill="#16a34a" rx={1} />
            <rect x={cx + 1} y={y(p.outflow)} width={barW} height={H - PAD_B - y(p.outflow)} fill="#dc2626" rx={1} />
            {i % labelEvery === 0 && (
              <text x={cx} y={H - 6} fontSize={9} fill="#6b7280" textAnchor="middle">
                {p.date.slice(5)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export default function Dashboard() {
  const [models, setModels] = useState<ModelDef[] | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [flow, setFlow] = useState<CashflowResp | null>(null);
  const [days, setDays] = useState(30);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api.models(), api.dashboard()])
      .then(([m, d]) => {
        setModels(m);
        const c: Record<string, number> = {};
        for (const row of d) c[row.model] = row.count;
        setCounts(c);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Failed to load'));
  }, []);

  useEffect(() => {
    api.cashflow(days).then(setFlow).catch(() => {});
  }, [days]);

  if (error) return <ErrorBox message={error} />;
  if (!models) return <Spinner />;

  const groups: Record<string, ModelDef[]> = {};
  for (const m of models) {
    const app = m.name.split('.')[0];
    (groups[app] ||= []).push(m);
  }

  return (
    <div>
      <h2 style={{ margin: '0 0 12px', fontSize: 18 }}>Dashboard</h2>

      <div className="stat-grid">
        <div className="stat green">
          <div className="label">💰 Total inflow ({flow?.days || days}d)</div>
          <div className="value">{flow ? formatMoney(flow.totals.inflow) : '…'}</div>
          <div className="sub">Completed wallet credits</div>
        </div>
        <div className="stat red">
          <div className="label">💸 Total outflow ({flow?.days || days}d)</div>
          <div className="value">{flow ? formatMoney(flow.totals.outflow) : '…'}</div>
          <div className="sub">Completed wallet debits</div>
        </div>
        <div className="stat amber">
          <div className="label">📊 Net flow ({flow?.days || days}d)</div>
          <div className="value">{flow ? formatMoney(flow.totals.net) : '…'}</div>
          <div className="sub">Inflow minus outflow</div>
        </div>
      </div>

      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <h3 style={{ margin: 0 }}>Cash inflow vs outflow</h3>
          <div style={{ flex: 1 }} />
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Range">
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
        <div className="chart-legend">
          <span><span className="swatch" style={{ background: '#16a34a' }} />Inflow (credit)</span>
          <span><span className="swatch" style={{ background: '#dc2626' }} />Outflow (debit)</span>
        </div>
        {flow ? <CashflowChart data={flow} /> : <Spinner label="Loading cashflow…" />}
      </div>

      {Object.entries(groups).map(([app, ms]) => (
        <div className="card" key={app}>
          <h3 style={{ textTransform: 'capitalize' }}>{app.replace(/_/g, ' ')}</h3>
          <div className="model-grid">
            {ms.map((m) => (
              <Link key={m.name} to={`/models/${encodeURIComponent(m.name)}`} className="model-card">
                <strong>{m.label}</strong>
                <span className="count">{counts[m.name] ?? '…'}</span>
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
