export async function api(path: string, data?: unknown) {
  const response = await fetch(`/api${path}`, {
    method: data === undefined ? 'GET' : 'POST',
    headers: data === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: data === undefined ? undefined : JSON.stringify(data),
    signal: AbortSignal.timeout(15000),
  });
  const result = await response.json().catch(() => { throw new Error('The backend is unavailable. Start it with npm run dev from the project root.'); });
  if (!response.ok) throw new Error(result.message || 'Request failed.');
  return result;
}
