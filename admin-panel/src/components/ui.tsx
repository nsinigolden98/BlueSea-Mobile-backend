import type { ReactNode } from 'react';

export function Pill({ tone, children }: { tone?: 'green' | 'red' | 'blue' | 'amber'; children: ReactNode }) {
  return <span className={tone ? `pill ${tone}` : 'pill'}>{children}</span>;
}

export function boolPill(v: unknown): ReactNode {
  if (v === true || v === 'true' || v === 't' || v === '1') return <Pill tone="green">Yes</Pill>;
  if (v === false || v === 'false' || v === 'f' || v === '0') return <Pill>No</Pill>;
  return <span style={{ color: '#9ca3af' }}>—</span>;
}

export function statusPill(v: unknown): ReactNode {
  const s = String(v ?? '').toUpperCase();
  if (['COMPLETED', 'APPROVED', 'ACTIVE', 'SUCCESS', 'PAID', 'VERIFIED'].includes(s))
    return <Pill tone="green">{String(v)}</Pill>;
  if (['FAILED', 'REJECTED', 'EXPIRED', 'CANCELLED', 'FROZEN', 'BLOCKED'].includes(s))
    return <Pill tone="red">{String(v)}</Pill>;
  if (['PENDING', 'PROCESSING', 'UPCOMING', 'IN_PROGRESS'].includes(s))
    return <Pill tone="amber">{String(v)}</Pill>;
  return <Pill tone="blue">{String(v)}</Pill>;
}

export function PageHeader({ trail, title, actions }: { trail?: ReactNode; title: string; actions?: ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
      <div>
        {trail && <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 2 }}>{trail}</div>}
        <h2 style={{ margin: 0, fontSize: 18 }}>{title}</h2>
      </div>
      <div style={{ flex: 1 }} />
      {actions}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return <div className="spinner">{label || 'Loading…'}</div>;
}

export function EmptyState({ label }: { label?: string }) {
  return <div className="empty">{label || 'No rows found.'}</div>;
}

export function ErrorBox({ message }: { message: string }) {
  return <div className="alert-error">{message}</div>;
}

export function formatMoney(n: number): string {
  return '₦' + n.toLocaleString('en-NG', { maximumFractionDigits: 2, minimumFractionDigits: n % 1 === 0 ? 0 : 2 });
}

export function formatCell(colType: string, colName: string, v: unknown): ReactNode {
  if (v === null || v === undefined || v === '') return <span style={{ color: '#9ca3af' }}>—</span>;
  if (colType === 'bool') return boolPill(v);
  if (colName === 'status' || colName === 'transaction_type') return statusPill(v);
  if (colType === 'datetime' || colType === 'date') {
    const d = new Date(String(v));
    if (!isNaN(d.getTime())) return d.toLocaleString('en-NG', { dateStyle: 'medium', timeStyle: colType === 'date' ? undefined : 'short' });
  }
  if (colType === 'json' || typeof v === 'object') {
    const s = JSON.stringify(v);
    return s.length > 60 ? s.slice(0, 60) + '…' : s;
  }
  const s = String(v);
  return s.length > 60 ? s.slice(0, 60) + '…' : s;
}
