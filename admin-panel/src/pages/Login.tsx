import { useState } from 'react';
import { useAuth } from '../auth';
import { ApiError } from '../api';

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed');
      if (err instanceof ApiError && err.status === 403) {
        setError('This account is not staff.');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <div className="login-card">
        <h2>BlueSea Admin</h2>
        <p className="sub">Staff accounts only.</p>
        <form onSubmit={submit}>
          <input
            placeholder="Email" value={email}
            onChange={(e) => setEmail(e.target.value)} autoComplete="email"
          />
          <input
            placeholder="Password" type="password" value={password}
            onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
          />
          {error && <div className="alert-error">{error}</div>}
          <button className="btn btn-primary" style={{ padding: 10 }} disabled={busy} type="submit">
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}
