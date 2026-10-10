// Typed client for the staff admin JSON API (src/admin/).
// Auth reuses the main JWT (Authorization: Bearer), gated on is_staff.

export interface ColumnDef {
  name: string;
  type: 'int' | 'bool' | 'numeric' | 'datetime' | 'date' | 'uuid' | 'json' | 'text';
}

export interface ModelDef {
  name: string;
  label: string;
  table: string;
  pk: string;
  pk_type: 'int' | 'uuid';
  columns: ColumnDef[];
  search: string[];
  default_order: string;
}

export interface ListResp {
  count: number;
  results: Record<string, unknown>[];
}

export interface CashflowPoint {
  date: string;
  inflow: number;
  outflow: number;
}

export interface CashflowResp {
  days: number;
  totals: { inflow: number; outflow: number; net: number };
  series: CashflowPoint[];
}

const TOKEN_KEY = 'bluesea_admin_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(typeof body === 'object' && body !== null && 'detail' in body
      ? String((body as Record<string, unknown>).detail)
      : `Request failed (${status})`);
    this.status = status;
    this.body = body;
  }
}

async function req(path: string, init?: RequestInit): Promise<unknown> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`/admin/api${path}`, {
    ...init,
    headers: { ...headers, ...(init?.headers as Record<string, string> | undefined) },
  });
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) throw new ApiError(res.status, body);
  return body;
}

export const api = {
  login: async (email: string, password: string): Promise<string> => {
    // Main auth endpoint (outside /admin); returns access + refresh tokens.
    const res = await fetch('/accounts/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const body = await res.json();
    if (!res.ok || !body.access_token) {
      throw new ApiError(res.status, body);
    }
    // Staff gate check happens on first admin call; verify eagerly here.
    setToken(body.access_token as string);
    try {
      await req('/models/');
    } catch (e) {
      setToken(null);
      throw e;
    }
    return body.access_token as string;
  },
  logout: () => setToken(null),
  models: () => req('/models/') as Promise<ModelDef[]>,
  dashboard: () => req('/dashboard/') as Promise<{ model: string; label: string; count: number }[]>,
  cashflow: (days = 30) => req(`/cashflow/?days=${days}`) as Promise<CashflowResp>,
  list: (model: string, params: Record<string, string>) => {
    const q = new URLSearchParams(params).toString();
    return req(`/${model}/?${q}`) as Promise<ListResp>;
  },
  get: (model: string, id: string) => req(`/${model}/${id}/`) as Promise<Record<string, unknown>>,
  create: (model: string, body: Record<string, unknown>) =>
    req(`/${model}/`, { method: 'POST', body: JSON.stringify(body) }),
  update: (model: string, id: string, body: Record<string, unknown>) =>
    req(`/${model}/${id}/`, { method: 'PUT', body: JSON.stringify(body) }),
  remove: (model: string, id: string) =>
    req(`/${model}/${id}/`, { method: 'DELETE' }),
  vendorAction: (id: string, action: 'approve' | 'reject', reason?: string) =>
    req(`/market_place.TicketVendor/${id}/${action}/`, {
      method: 'POST',
      body: JSON.stringify(action === 'reject' ? { reason } : {}),
    }),
};

export function displayValue(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'boolean') return v ? 'Yes' : 'No';
  if (typeof v === 'object') return JSON.stringify(v);
  const s = String(v);
  return s.length > 80 ? s.slice(0, 80) + '…' : s;
}
