import React, { useEffect, useMemo, useState } from 'react';
import { GoogleMap, useJsApiLoader, MarkerF, PolylineF } from '@react-google-maps/api';
import { api } from '../api';

type Point = { lat: number; lng: number };
type Endpoint = Point & { label: string };
type Corridor = { id: string; name: string; origin: Endpoint; destination: Endpoint; supporters: number; realSupporters: number; exampleSupporters: number; stage: 'gathering' | 'review'; progress: number; supportedByMe: boolean };
type Demand = { corridors: Corridor[]; threshold: number; totals: { supporters: number; corridors: number; ready: number }; includesExamples: boolean };
const center = { lat: 35.145, lng: -89.975 };
const bounds = { north: 35.4, south: 34.85, west: -90.3, east: -89.6 };
const mapStyle = { width: '100%', height: '100%' };
const colors = ['#15756a', '#df8750', '#7278b8', '#4195ad', '#b6a552'];
const options = { restriction: { latLngBounds: bounds, strictBounds: false }, mapTypeControl: false, streetViewControl: false, fullscreenControl: false, clickableIcons: false, styles: [
  { featureType: 'poi', stylers: [{ visibility: 'off' }] },
  { featureType: 'transit', stylers: [{ visibility: 'off' }] },
  { featureType: 'landscape', stylers: [{ color: '#eff0e9' }] },
  { featureType: 'water', stylers: [{ color: '#bad8da' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#ffffff' }] },
  { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#dfdfd1' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#6c7976' }] },
] };

function curvedPath(a: Point, b: Point) {
  if (a.lat === b.lat && a.lng === b.lng) return Array.from({ length: 33 }, (_, i) => ({ lat: a.lat + .002 * Math.sin(i / 32 * 2 * Math.PI), lng: a.lng + .0025 * Math.cos(i / 32 * 2 * Math.PI) }));
  const dx = b.lng - a.lng, dy = b.lat - a.lat;
  const mid = { lat: (a.lat + b.lat) / 2 + dx * .15, lng: (a.lng + b.lng) / 2 - dy * .15 };
  return Array.from({ length: 33 }, (_, i) => { const t = i / 32; return { lat: (1 - t) ** 2 * a.lat + 2 * (1 - t) * t * mid.lat + t * t * b.lat, lng: (1 - t) ** 2 * a.lng + 2 * (1 - t) * t * mid.lng + t * t * b.lng }; });
}

export default function MapComponent({ userId, onLogout }: { userId: string; onLogout: () => void }) {
  const { isLoaded, loadError } = useJsApiLoader({ googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '' });
  const [view, setView] = useState<'request' | 'demand'>(new URLSearchParams(location.search).get('view') === 'demand' ? 'demand' : 'request');
  const [pickup, setPickup] = useState<Point | null>(null);
  const [dropoff, setDropoff] = useState<Point | null>(null);
  const [editing, setEditing] = useState<'pickup' | 'dropoff'>('pickup');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [demandError, setDemandError] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [demand, setDemand] = useState<Demand | null>(null);
  const [examples, setExamples] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState('');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<'all' | 'review' | 'mine'>('all');
  const [map, setMap] = useState<google.maps.Map | null>(null);

  useEffect(() => {
    let active = true; setLoading(true); setDemandError('');
    api(`/demand?examples=${examples ? 1 : 0}`).then(result => { if (active) setDemand(result); })
      .catch(e => { if (active) setDemandError(e.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [examples, refresh]);

  const corridors = demand?.corridors || [];
  const filtered = useMemo(() => corridors.filter(c => c.name.toLowerCase().includes(query.toLowerCase()) && (filter !== 'review' || c.stage === 'review') && (filter !== 'mine' || c.supportedByMe)), [demand, query, filter]);
  const selected = filtered.find(c => c.id === selectedId) || filtered[0];
  const visible = filtered.slice(0, 5);
  if (selected && !visible.some(c => c.id === selected.id)) visible[4] = selected;

  useEffect(() => {
    if (!map || !isLoaded) return;
    const points = view === 'request' ? (pickup && dropoff ? curvedPath(pickup, dropoff) : []) : visible.flatMap(c => curvedPath(c.origin, c.destination));
    if (points.length > 1) { const box = new google.maps.LatLngBounds(); points.forEach(p => box.extend(p)); map.fitBounds(box, 75); }
  }, [map, isLoaded, view, demand, selectedId, query, filter, pickup, dropoff]);

  async function submit() {
    if (!pickup || !dropoff || busy) return;
    setBusy(true); setError('');
    try {
      const result = await api('/submit', { start_lat: pickup.lat, start_lng: pickup.lng, end_lat: dropoff.lat, end_lng: dropoff.lng });
      setConfirmation(`Request #${result.route.id} submitted. Your route has been added.`);
      setSelectedId(result.corridorId); setQuery(''); setFilter('all'); setRefresh(n => n + 1); setView('demand');
      setPickup(null); setDropoff(null); setEditing('pickup');
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to submit. Please try again.'); }
    finally { setBusy(false); }
  }
  function choose(point: Point) {
    if (busy) return;
    setError('');
    if (editing === 'pickup') { setPickup(point); setEditing('dropoff'); } else setDropoff(point);
  }
  function requestCorridor(c: Corridor) {
    const local = c.origin.lat === c.destination.lat && c.origin.lng === c.destination.lng;
    setPickup(local ? { lat: c.origin.lat, lng: c.origin.lng - .001 } : c.origin); setDropoff(local ? { lat: c.destination.lat, lng: c.destination.lng + .001 } : c.destination); setEditing('dropoff'); setView('request'); setError(''); setConfirmation('');
  }
  const ready = Boolean(pickup && dropoff);

  return <div className="app-shell">
    <header className="app-header">
      <a href="/" className="brand" aria-label="Memphis in Motion home"><span className="brand-mark">m<span>↗</span></span><span>memphis<span className="brand-sub">in motion</span></span></a>
      <nav className="view-tabs" aria-label="Main navigation">
        <button className={view === 'request' ? 'active' : ''} onClick={() => setView('request')}>Request a route</button>
        <button className={view === 'demand' ? 'active' : ''} onClick={() => setView('demand')}>Requested routes</button>
      </nav>
      <div className="account-menu"><span className="avatar">{userId.slice(0, 1).toUpperCase()}</span><button className="text-button" onClick={async () => { try { await api('/logout', {}); onLogout(); } catch (e) { setError(e instanceof Error ? e.message : 'Unable to log out.'); } }}>Log out</button></div>
    </header>
    <main className="workspace">
      <div className="page-heading"><div><h1>{view === 'request' ? 'Request a bus route' : 'Requested routes'}</h1><p>{view === 'request' ? 'Choose your pickup and destination, then submit your request.' : 'See which routes people in Memphis are requesting.'}</p></div><span className="concept-tag"><span /> Demo</span></div>
      {confirmation && view === 'demand' && <div className="confirmation" role="status"><span className="checkmark">✓</span><div><strong>{confirmation}</strong><p>Saved in this demo. Requests are not sent to MATA.</p></div><button className="text-button" aria-label="Dismiss confirmation" onClick={() => setConfirmation('')}>×</button></div>}
      {error && <p className="error-message" role="alert">{error}</p>}
      <div className="dashboard-layout">
        <aside className="sidebar">
          {view === 'request' ? <>
            <div className="panel-heading"><h2>Your trip</h2><p>Click the map to set each location.</p></div>
            <div className="journey-inputs">
              <button className={`location-input ${editing === 'pickup' ? 'selected' : ''}`} onClick={() => setEditing('pickup')} disabled={busy}><span className="point-letter">A</span><span><strong>Pickup</strong><small>{pickup ? `${pickup.lat.toFixed(4)}, ${pickup.lng.toFixed(4)}` : 'Click your starting point on the map'}</small></span>{pickup && <span className="point-check">✓</span>}</button>
              <div className="journey-connector" />
              <button className={`location-input ${editing === 'dropoff' ? 'selected' : ''}`} onClick={() => setEditing('dropoff')} disabled={busy}><span className="point-letter destination">B</span><span><strong>Destination</strong><small>{dropoff ? `${dropoff.lat.toFixed(4)}, ${dropoff.lng.toFixed(4)}` : 'Where do you want to go?'}</small></span>{dropoff && <span className="point-check">✓</span>}</button>
            </div>
            <div className="request-actions"><button className="primary-button" onClick={submit} disabled={!ready || busy}>{busy ? 'Submitting your request…' : 'Submit route request'}<span>↗</span></button><button className="text-button" disabled={busy || (!pickup && !dropoff)} onClick={() => { setPickup(null); setDropoff(null); setEditing('pickup'); setError(''); }}>Reset points</button></div>
            <div className="how-it-works"><p className="eyebrow">HOW IT WORKS</p><ol><li><span>1</span><div><strong>Choose your locations</strong><p>Select a pickup and destination.</p></div></li><li><span>2</span><div><strong>Submit your request</strong><p>Similar trips are grouped into one route.</p></div></li><li><span>3</span><div><strong>See the request count</strong><p>Popular routes are marked for review.</p></div></li></ol></div>
            <button className="sample-trip" disabled={busy} onClick={() => { const c = corridors.find(c => c.name.includes('Downtown') && c.name.includes('University'));  if (c) requestCorridor(c); else { setPickup({ lat: 35.1495, lng: -90.049 }); setDropoff({ lat: 35.1188, lng: -89.937 }); } }}>Try a sample route <span>→</span></button>
          </> : <>
            <div className="panel-heading"><h2>Routes by request count</h2><p>Similar trips are grouped together. Each account counts once per route.</p></div>
            <div className="data-switch"><label><input type="checkbox" checked={examples} onChange={e => setExamples(e.target.checked)} /> Show sample requests</label><p>{examples ? 'Includes sample counts for the demo.' : 'Showing saved requests only.'}</p></div>
            <label className="search-field"><span className="sr-only">Search routes</span><span aria-hidden="true">⌕</span><input placeholder="Search by neighborhood" value={query} onChange={e => setQuery(e.target.value)} /></label>
            <div className="filter-tabs" aria-label="Filter routes">{([['all', 'All routes'], ['review', 'Ready for review'], ['mine', 'My requests']] as const).map(([value, label]) => <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{label}</button>)}</div>
            <div className="corridor-list" aria-busy={loading}>
              {loading ? <p className="empty-state">Loading routes…</p> : demandError ? <div className="empty-state" role="alert"><p>{demandError}</p><button onClick={() => setRefresh(n => n + 1)}>Retry</button></div> : filtered.length === 0 ? <div className="empty-state"><strong>No routes found.</strong><p>{query || filter !== 'all' ? 'Try another search or filter.' : 'Submit a route to add it here.'}</p><button onClick={() => setView('request')}>Request a route</button></div> : filtered.map((c, i) => <button key={c.id} className={`corridor-card ${selected?.id === c.id ? 'selected' : ''}`} onClick={() => setSelectedId(c.id)}>
                <div className="corridor-topline"><span className="corridor-rank">{String(i + 1).padStart(2, '0')}</span><span className={`stage-pill ${c.stage}`}>{c.stage === 'review' ? 'Ready for review' : 'Collecting requests'}</span>{c.supportedByMe && <span className="my-request" title="You requested this route">✓ Yours</span>}</div>
                <h3>{c.origin.label}<span>↔</span>{c.destination.label}</h3>
                <div className="support-row"><span><strong>{c.supporters}</strong> requests</span><small>{Math.max(0, (demand?.threshold || 100) - c.supporters) ? `${(demand?.threshold || 100) - c.supporters} to review` : 'Ready for review'}</small></div>
                <div className="progress-track" role="progressbar" aria-label={`${c.name} requests toward review`} aria-valuenow={Math.min(c.supporters, demand?.threshold || 100)} aria-valuemin={0} aria-valuemax={demand?.threshold || 100}><span style={{ width: `${c.progress}%` }} /></div>
                {c.exampleSupporters > 0 && <small className="example-count">Includes {c.exampleSupporters} sample requests</small>}
              </button>)}
            </div>
            <p className="sidebar-footnote">{demand?.threshold || 100} requests mark a route for review in this demo. This is not a MATA rule.</p>
          </>}
        </aside>
        <section className="map-column" aria-label={view === 'request' ? 'Select your trip on the Memphis map' : 'Map of requested Memphis routes'}>
          {view === 'demand' && <div className="demand-stats"><div><strong>{loading || demandError ? '—' : demand?.totals.supporters || 0}</strong><span>Requests</span></div><div><strong>{loading || demandError ? '—' : demand?.totals.corridors || 0}</strong><span>Routes</span></div><div><strong>{loading || demandError ? '—' : demand?.totals.ready || 0}</strong><span>Ready for review</span></div>{examples && <span className="stats-demo">INCLUDES SAMPLE DATA</span>}</div>}
          <div className={`map-canvas ${view === 'demand' ? 'demand-map' : ''}`}>
            {loadError ? <div className="map-loading" role="alert">The map couldn’t load. Please refresh and try again.</div> : !isLoaded ? <div className="map-loading">Loading Memphis…</div> : <GoogleMap mapContainerStyle={mapStyle} center={center} zoom={12} options={options} onLoad={setMap} onUnmount={() => setMap(null)} onClick={e => { if (view === 'request' && e.latLng) choose(e.latLng.toJSON()); }}>
              {view === 'request' && pickup && <MarkerF position={pickup} label={{ text: 'A', color: 'white', fontWeight: '700' }} icon={{ path: google.maps.SymbolPath.CIRCLE, scale: 16, fillColor: '#15756a', fillOpacity: 1, strokeColor: '#fff', strokeWeight: 3 }} />}
              {view === 'request' && dropoff && <MarkerF position={dropoff} label={{ text: 'B', color: 'white', fontWeight: '700' }} icon={{ path: google.maps.SymbolPath.CIRCLE, scale: 16, fillColor: '#df8750', fillOpacity: 1, strokeColor: '#fff', strokeWeight: 3 }} />}
              {view === 'request' && pickup && dropoff && <PolylineF path={curvedPath(pickup, dropoff)} options={{ strokeColor: '#15756a', strokeWeight: 5, strokeOpacity: .8, clickable: false }} />}
              {view === 'demand' && !loading && !demandError && visible.map((c, i) => <React.Fragment key={c.id}>
                <PolylineF path={curvedPath(c.origin, c.destination)} options={{ strokeColor: colors[i % colors.length], strokeWeight: 3 + Math.min(c.supporters / 25, 5), strokeOpacity: c.id === selected?.id ? .95 : .42, zIndex: c.id === selected?.id ? 3 : 1 }} onClick={() => setSelectedId(c.id)} />
                {[c.origin, c.destination].map((p, j) => <MarkerF key={j} position={p} title={p.label} onClick={() => setSelectedId(c.id)} icon={{ path: google.maps.SymbolPath.CIRCLE, scale: c.id === selected?.id ? 7 : 4, fillColor: colors[i % colors.length], fillOpacity: c.id === selected?.id ? 1 : .5, strokeColor: 'white', strokeWeight: 2 }} />)}
              </React.Fragment>)}
            </GoogleMap>}
            <div className="map-instruction">{view === 'request' ? <><span className={`instruction-dot ${editing === 'dropoff' ? 'orange' : ''}`} />{ready ? 'Both locations selected. You can submit your request.' : `Click the map to choose your ${editing === 'pickup' ? 'pickup' : 'destination'}.`}</> : <><span className="instruction-dot" />{Math.min(5, filtered.length)} routes shown · Select a route to highlight it</>}</div>
            {view === 'demand' && selected && !loading && !demandError && <div className="map-detail"><div className="detail-heading"><div><p className="eyebrow">SELECTED ROUTE</p><h2>{selected.name}</h2></div><span className="detail-count">{selected.supporters}<small>requests</small></span></div><div className="milestone-steps"><span className="complete">● Requested</span><i /><span className={selected.stage === 'review' ? 'complete' : ''}>● Review</span><i /><span>○ Planning</span><i /><span>○ Trial service</span></div><p>{selected.stage === 'review' ? 'This route has enough requests for review in the demo. A transit agency would decide whether to add service.' : `${Math.max(0, (demand?.threshold || 100) - selected.supporters)} more requests needed for review in this demo.`}</p><button className="text-button" onClick={() => requestCorridor(selected)}>{selected.supportedByMe ? 'View route' : 'Request this route'} <span>↗</span></button></div>}
            <div className="map-legend"><span className="legend-line" />{view === 'demand' ? 'Thicker lines = more requests' : 'Requested route'}<span className="legend-divider" />Lines connect areas; they don’t follow roads</div>
          </div>
        </section>
      </div>
      <footer className="app-footer"><span>Demo · Requests are not sent to MATA.</span></footer>
    </main>
  </div>;
}
