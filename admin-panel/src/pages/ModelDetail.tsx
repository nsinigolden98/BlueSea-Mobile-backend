import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ApiError, api, type ColumnDef, type ModelDef } from '../api';
import { ErrorBox, PageHeader, Spinner } from '../components/ui';

function FieldInput({ col, value, onChange }: { col: ColumnDef; value: unknown; onChange: (v: unknown) => void }) {
  if (col.type === 'bool') {
    const tri = value === null || value === undefined ? '' : String(value);
    return (
      <select value={tri} onChange={(e) => onChange(e.target.value === '' ? null : e.target.value === 'true')}>
        <option value="">—</option>
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select>
    );
  }
  if (col.type === 'json') {
    return (
      <textarea
        rows={3} cols={50}
        value={typeof value === 'object' ? JSON.stringify(value ?? null) : String(value ?? '')}
        onChange={(e) => {
          try {
            onChange(e.target.value.trim() === '' ? null : JSON.parse(e.target.value));
          } catch {
            onChange(e.target.value);
          }
        }}
      />
    );
  }
  if (col.name === 'password') {
    return <input type="password" value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} placeholder={value ? '(unchanged if empty)' : ''} />;
  }
  if (col.type === 'text' && col.name.includes('message')) {
    return (
      <textarea
        rows={3} cols={50}
        value={value === null || value === undefined ? '' : String(value)}
        onChange={(e) => onChange(e.target.value === '' ? null : e.target.value)}
      />
    );
  }
  return (
    <input
      style={{ width: '100%', maxWidth: 420 }}
      value={value === null || value === undefined ? '' : String(value)}
      onChange={(e) => onChange(e.target.value === '' ? null : e.target.value)}
      placeholder={col.type}
    />
  );
}

export default function ModelDetail({ mode }: { mode: 'view' | 'new' }) {
  const { name = '', id = '' } = useParams();
  const model = decodeURIComponent(name);
  const navigate = useNavigate();
  const [def, setDef] = useState<ModelDef | null>(null);
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');

  useEffect(() => {
    api.models()
      .then((models) => {
        const d = models.find((m) => m.name === model);
        if (!d) {
          setError(`Unknown model ${model}`);
          return;
        }
        setDef(d);
        if (mode === 'view') {
          api.get(model, decodeURIComponent(id))
            .then((row) => setForm(row as Record<string, unknown>))
            .catch((e) => setError(e instanceof ApiError ? e.message : 'Failed to load'));
        }
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Failed to load'));
  }, [model, id, mode]);

  const save = async () => {
    setError('');
    setSaved('');
    try {
      // Never send an empty password (means "unchanged"); never send the pk.
      const body: Record<string, unknown> = { ...form };
      if (body.password === null || body.password === '') delete body.password;
      if (!def) return;
      delete body[def.pk];
      if (mode === 'new') {
        const created = (await api.create(model, body)) as Record<string, unknown>;
        navigate(`/models/${encodeURIComponent(model)}/${encodeURIComponent(String(created.id))}`);
      } else {
        const row = (await api.update(model, decodeURIComponent(id), body)) as Record<string, unknown>;
        setForm(row);
        setSaved('Saved.');
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Save failed');
    }
  };

  const remove = async () => {
    if (!def || !window.confirm(`Delete this ${def.label} row?`)) return;
    try {
      await api.remove(model, decodeURIComponent(id));
      navigate(`/models/${encodeURIComponent(model)}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Delete failed');
    }
  };

  const vendorAction = async (action: 'approve' | 'reject') => {
    let reason: string | undefined;
    if (action === 'reject') {
      reason = window.prompt('Rejection reason (required):') || '';
      if (!reason.trim()) return;
    }
    try {
      await api.vendorAction(decodeURIComponent(id), action, reason);
      const row = (await api.get(model, decodeURIComponent(id))) as Record<string, unknown>;
      setForm(row);
      setSaved(action === 'approve' ? 'Vendor approved.' : 'Vendor rejected.');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Action failed');
    }
  };

  if (error) return <ErrorBox message={error} />;
  if (!def) return <Spinner />;

  const isVendor = model === 'market_place.TicketVendor';

  return (
    <div>
      <PageHeader
        trail={<><Link to="/">Admin</Link> / <Link to={`/models/${encodeURIComponent(model)}`}>{def.label}</Link></>}
        title={mode === 'new' ? `Add ${def.label}` : `${def.label} #${String(form[def.pk] ?? '')}`}
      />
      {isVendor && mode === 'view' && (
        <div className="card" style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" onClick={() => void vendorAction('approve')}>✓ Approve vendor</button>
          <button className="btn btn-danger" onClick={() => void vendorAction('reject')}>✕ Reject vendor…</button>
        </div>
      )}
      <div className="card">
        <div className="form-grid">
          {def.columns.map((c) => (
            <div className="form-row" key={c.name}>
              <div className="form-label">
                {c.name}
                <span className="type">{c.type}{c.name === def.pk ? ' · primary key' : ''}</span>
              </div>
              <div className="form-input">
                {c.name === def.pk && mode === 'view' ? (
                  <strong>{String(form[c.name] ?? '')}</strong>
                ) : (
                  <FieldInput col={c} value={form[c.name]} onChange={(v) => setForm({ ...form, [c.name]: v })} />
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
      {saved && <div className="alert-ok">{saved}</div>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn btn-primary" onClick={() => void save()}>{mode === 'new' ? 'Create' : 'Save'}</button>
        {mode === 'view' && (
          <button className="btn btn-danger" onClick={() => void remove()}>
            Delete
          </button>
        )}
      </div>
    </div>
  );
}
