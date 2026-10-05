"""Local route-request API. Run behind the frontend's /api proxy."""
import math
from contextlib import contextmanager
import os
import secrets
import sqlite3
from pathlib import Path
from flask import Flask, jsonify, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from demand import aggregate_demand, corridor_id_for, distance_meters, in_memphis, MIN_TRIP_METERS


def create_app(database=None):
    app = Flask(__name__)
    root = Path(__file__).parent
    key_file = root / '.session-key'
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
        key_file.chmod(0o600)
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or key_file.read_text(),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      MAX_CONTENT_LENGTH=16384)
    db_path = database or str(root / 'routes.sqlite3')

    @contextmanager
    def connect():
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS routes (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
          start_lat REAL NOT NULL, start_lng REAL NOT NULL,
          end_lat REAL NOT NULL, end_lng REAL NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          status TEXT NOT NULL DEFAULT 'submitted');
        ''')

    @app.post('/register')
    def register():
        data = request.get_json(silent=True) or {}
        user_id, password = data.get('id', ''), data.get('password', '')
        if not isinstance(user_id, str) or not isinstance(password, str):
            return jsonify(message='Enter a user ID and password.'), 400
        user_id = user_id.strip()
        if not 3 <= len(user_id) <= 80 or not 8 <= len(password) <= 256:
            return jsonify(message='Use a 3–80 character ID and an 8–256 character password.'), 400
        try:
            with connect() as db:
                db.execute('INSERT INTO users VALUES (?, ?)', (user_id, generate_password_hash(password)))
        except sqlite3.IntegrityError:
            return jsonify(message='That user ID is already registered.'), 409
        session.clear()
        session['user_id'] = user_id
        return jsonify(userId=user_id), 201

    @app.post('/login')
    def login():
        data = request.get_json(silent=True) or {}
        user_id, password = data.get('id'), data.get('password')
        if not isinstance(user_id, str) or not isinstance(password, str):
            return jsonify(message='Enter your user ID and password.'), 400
        with connect() as db:
            user = db.execute('SELECT * FROM users WHERE id = ?', (user_id.strip(),)).fetchone()
        if not user or not check_password_hash(user['password'], password):
            return jsonify(message='Incorrect user ID or password.'), 401
        session.clear()
        session['user_id'] = user['id']
        return jsonify(userId=user['id'])

    @app.get('/session')
    def current_session():
        return jsonify(userId=session.get('user_id'))

    @app.post('/logout')
    def logout():
        session.clear()
        return jsonify(message='Signed out.')

    @app.post('/submit')
    def submit():
        user_id = session.get('user_id')
        if not user_id:
            return jsonify(message='Please log in before submitting.'), 401
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify(message='Select valid pickup and dropoff coordinates.'), 400
        fields = ('start_lat', 'start_lng', 'end_lat', 'end_lng')
        values = [data.get(field) for field in fields]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            return jsonify(message='Select valid pickup and dropoff coordinates.'), 400
        if any(not -90 <= values[i] <= 90 for i in (0, 2)) or any(not -180 <= values[i] <= 180 for i in (1, 3)):
            return jsonify(message='Coordinates are outside valid ranges.'), 400
        if not in_memphis(*values[:2]) or not in_memphis(*values[2:]):
            return jsonify(message='Choose pickup and dropoff locations in the Memphis area.'), 400
        if distance_meters(values[:2], values[2:]) < MIN_TRIP_METERS:
            return jsonify(message='Choose pickup and dropoff locations at least 150 meters apart.'), 400
        with connect() as db:
            cursor = db.execute('INSERT INTO routes (user_id, start_lat, start_lng, end_lat, end_lng) VALUES (?, ?, ?, ?, ?)', (user_id, *values))
            route = dict(db.execute('SELECT * FROM routes WHERE id = ?', (cursor.lastrowid,)).fetchone())
        return jsonify(route=route, corridorId=corridor_id_for(*values), message='Your route request was added to community demand.'), 201

    @app.get('/demand')
    def demand():
        with connect() as db:
            rows = db.execute('SELECT user_id, start_lat, start_lng, end_lat, end_lng FROM routes').fetchall()
        return jsonify(aggregate_demand(rows, session.get('user_id'), request.args.get('examples') == '1'))

    @app.get('/routes')
    def routes():
        if not session.get('user_id'):
            return jsonify(message='Please log in.'), 401
        with connect() as db:
            rows = db.execute('SELECT * FROM routes WHERE user_id = ? ORDER BY id DESC', (session['user_id'],)).fetchall()
        return jsonify(routes=[dict(row) for row in rows])

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=int(os.environ.get('PORT', 10000)))
