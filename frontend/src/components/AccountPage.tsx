import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function AccountPage({ register = false, onLogin }: { register?: boolean; onLogin: (id: string) => void }) {
  const [id, setId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const result = await api(register ? '/register' : '/login', { id, password });
      onLogin(result.userId); navigate('/');
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to connect.'); }
    finally { setBusy(false); }
  }
  return <main className="account"><form className="card" onSubmit={submit}>
    <p className="eyebrow">MEMPHIS IN MOTION</p>
    <h1>{register ? 'Create your account' : 'Log in'}</h1>
    <p>Request a bus route and see routes other people have requested.</p>
    <label>User ID<input value={id} onChange={e => setId(e.target.value)} required minLength={3} maxLength={80} autoComplete="username" /></label>
    <label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={8} maxLength={256} autoComplete={register ? 'new-password' : 'current-password'} /></label>
    {error && <p role="alert">{error}</p>}
    <button disabled={busy}>{busy ? 'Please wait…' : register ? 'Create account' : 'Log in'}</button>
    <Link to={register ? '/login' : '/register'}>{register ? 'Already registered? Log in' : 'New here? Create an account'}</Link>
  </form></main>;
}
