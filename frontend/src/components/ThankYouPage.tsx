import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
type SavedRoute = { id: number; start_lat: number; start_lng: number; end_lat: number; end_lng: number; status: string; created_at: string };
export default function ThankYouPage() {
  const [routes, setRoutes] = useState<SavedRoute[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => { api('/routes').then(result => setRoutes(result.routes)).catch(e => setError(e.message)).finally(() => setLoading(false)); }, []);
  return <main className="account"><section className="card">
    <p className="eyebrow">YOUR ROUTE REQUESTS</p><h1>Request received</h1>
    <p>Your request has been saved. This prototype records requests; it does not dispatch a ride.</p>
    {loading && <p>Loading saved requests…</p>}{error && <p role="alert">{error}</p>}
    {routes.map(route => <article className="route-card" key={route.id}>
      <strong>Request #{route.id} · {route.status}</strong>
      <p>Pickup: {route.start_lat.toFixed(5)}, {route.start_lng.toFixed(5)}</p>
      <p>Dropoff: {route.end_lat.toFixed(5)}, {route.end_lng.toFixed(5)}</p>
      <small>Saved {route.created_at} UTC</small>
    </article>)}
    <Link to="/">Choose another route</Link>
  </section></main>;
}
