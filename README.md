# Memphis in Motion · Fronthacks

A community transit planning concept for Memphis. Residents suggest pickup and destination points, then see the shared corridors those journeys form. Requests are saved locally; no requests are transmitted to MATA, and the project has no MATA affiliation.

## Run

Requires Node.js, npm, Python 3, and a working Google Maps JavaScript API key.

From the repository root:

```sh
npm run setup
npm run dev
```

Put your Google Maps key in `frontend/.env`:

```env
VITE_GOOGLE_MAPS_API_KEY=your_key
```

Open http://localhost:3000. Stop any earlier frontend dev server first so port 3000 is available. Register an account with a user ID and password, select two locations, and submit. Submission opens the community demand dashboard, highlights your corridor, and confirms that your request was recorded. Use “My requests” to see the connections you support. Restarting the backend preserves accounts and routes.

## Backend

Flask listens on 127.0.0.1:10000. Vite proxies `/api` to Flask, including session cookies. SQLite data lives in `backend/routes.sqlite3`, separate from legacy Airtable data. Passwords are hashed; the backend derives route ownership from the signed session rather than trusting a submitted user ID.

Endpoints: POST `/register`, `/login`, `/logout`, `/submit`; GET `/session`, `/routes`, `/demand`. Coordinates are validated, and route history only returns the current user's records. No Airtable credentials or hosted Render service are required.

For deployment, use a production WSGI server, HTTPS with secure session cookies, a same-origin `/api` reverse proxy, durable database storage, and rate limiting. The current launcher is for local demos.

## Community demand

The map displays at most five corridors at once. Select a ranked card to bring any other corridor into view; search by neighborhood or filter for review-ready corridors and your own requests. Line width represents support, while the selected corridor is highlighted. Lines represent suggested connections, not road routing or existing bus services.

Requests are grouped by approximately 1 km pickup and destination grid cells. Reverse journeys count toward the same connection. Each account contributes at most one supporter per corridor, even after repeated submissions. Distinct accounts are a demonstration of support, not verified distinct residents. Nearby requests on opposite sides of a grid boundary can land in separate corridors; this is a simple spatial grouping prototype, not a service-planning optimizer.

Public demand uses coarse cell centers and approximate neighborhood names; personal coordinates and account IDs are excluded. Very short local connections may share a center and appear as loops on the map. Requests must be within the Memphis-area bounding box and at least 150 meters long.

“Show sample requests” is on by default to make the concept demonstrable. Six sample corridors are clearly labeled, computed on read, and never stored as fake user requests. Turn it off to see only saved community support. The total counts support across corridors, so one account can contribute to more than one connection.

At 100 supporters, a corridor becomes **Ready for review**. This is a demo rule, not a MATA policy. Planning and pilot stages illustrate what could come next; they do not advance automatically or promise service implementation.

## Verify

```sh
npm test
npm run build
cd frontend && npx tsc --noEmit
```

For portfolio media, record selecting pickup/dropoff and submitting; capture the community demand dashboard showing the highlighted corridor and review progress. “Try a sample route” fills Downtown–University District to make the flow easy to demonstrate.


## Captured demo media

- [Choose and submit a route](demo-media/01-request-route.png) — [video](demo-media/01-request-route.webm)
- [Explore community demand](demo-media/02-community-demand.png) — [video](demo-media/02-explore-demand.webm)

These captures use the labeled illustrative demand plus temporary browser-test requests. Test accounts were removed after verification.
