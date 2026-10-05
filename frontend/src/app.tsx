import React, { useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import MapComponent from './components/MapComponent';
import AccountPage from './components/AccountPage';
import { api } from './api';
import './styles.css';

export default function App() {
  const [userId, setUserId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => { api('/session').then(result => setUserId(result.userId)).catch(() => setError('Backend unavailable. Start npm run dev from the Fronthacks root, then reload.')).finally(() => setLoading(false)); }, []);
  if (loading) return <main className="account">Loading…</main>;
  if (error) return <main className="account"><div className="card"><h1>Unable to connect</h1><p role="alert">{error}</p><button onClick={() => location.reload()}>Retry</button></div></main>;
  return <Routes>
    <Route path="/" element={userId ? <MapComponent userId={userId} onLogout={() => setUserId(null)} /> : <Navigate to="/login" replace />} />
    <Route path="/login" element={<AccountPage onLogin={setUserId} />} />
    <Route path="/register" element={<AccountPage register onLogin={setUserId} />} />
    <Route path="/thank-you" element={userId ? <Navigate to="/?view=demand" replace /> : <Navigate to="/login" replace />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>;
}
