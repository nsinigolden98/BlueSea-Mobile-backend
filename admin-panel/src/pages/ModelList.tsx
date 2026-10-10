import { useCallback, useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ApiError, api, type ModelDef } from '../api';
import { EmptyState, ErrorBox, PageHeader, Spinner, formatCell } from '../components/ui';

const PAGE_SIZE = 25;

function humanize(col: string): string {
  return col.replace(/_id$/, '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function ModelList() {
  const { name = '' } = useParams();
  const model = decodeURIComponent(name);
  const [searchParams, setSearchParams] = useSearchParams();
  const [def, setDef] = useState<ModelDef | null>(null);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [count, setCount] = useState(0);
  const [error, setError] = useState('');

  const page = Math.max(1, parseInt(searchParams.get('page') || '1', 10) || 1);
  const search = searchParams.get('search') || '';

  const load = useCallback(async () => {
    setError('');
    try {
      const models = await api.models();
      const d = models.find((m) => m.name === model);
      if (!d) {
        setError(`Unknown model ${model}`);
        return;
      }
      setDef(d);
      const list = await api.list(model, {
        page: String(page),
        page_size: String(PAGE_SIZE),
        ...(search ? { search } : {}),
      });
      setRows(list.results);
      setCount(list.count);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to load');
    }
  }, [model, page, search]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <ErrorBox message={error} />;
  if (!def) return <Spinner />;

  const cols = def.columns.filter((c) => !['password', 'transaction_pin'].includes(c.name));
  const pages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  return (
    <div>
      <PageHeader
        trail={<><Link to="/">Admin</Link> / {def.label}</>}
        title={`${def.label} (${count.toLocaleString()})`}
        actions={<Link className="btn btn-primary" to={`/models/${encodeURIComponent(model)}/new`}>+ Add {def.label}</Link>}
      />
      <div className="toolbar">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const q = (new FormData(e.target as HTMLFormElement).get('q') as string) || '';
            setSearchParams(q ? { search: q, page: '1' } : { page: '1' });
          }}
        >
          <input name="q" defaultValue={search} placeholder={`Search ${def.label}…`} />
          <button className="btn" type="submit" style={{ marginLeft: 6 }}>Go</button>
        </form>
      </div>
      {rows.length === 0 ? (
        <div className="card"><EmptyState label={search ? `No results for "${search}".` : `No ${def.label} rows yet.`} /></div>
      ) : (
        <div className="table-wrap">
          <table className="grid">
            <thead>
              <tr>
                {cols.map((c) => (
                  <th key={c.name}>{humanize(c.name)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={String(r[def.pk])}>
                  {cols.map((c, i) => (
                    <td key={c.name} title={String(r[c.name] ?? '')}>
                      {i === 0 ? (
                        <Link to={`/models/${encodeURIComponent(model)}/${encodeURIComponent(String(r[def.pk]))}`}>
                          {formatCell(c.type, c.name, r[c.name])}
                        </Link>
                      ) : (
                        formatCell(c.type, c.name, r[c.name])
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="pager">
        <button className="btn" disabled={page <= 1} onClick={() => setSearchParams({ ...(search ? { search } : {}), page: String(page - 1) })}>
          ‹ Prev
        </button>
        <span>Page {page} of {pages}</span>
        <button className="btn" disabled={page >= pages} onClick={() => setSearchParams({ ...(search ? { search } : {}), page: String(page + 1) })}>
          Next ›
        </button>
      </div>
    </div>
  );
}
