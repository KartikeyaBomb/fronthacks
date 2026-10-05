import tempfile
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from app import create_app


MEMPHIS_TRIP = {'start_lat': 35.1495, 'start_lng': -90.049,
                'end_lat': 35.118, 'end_lng': -89.937}


class RouteFlowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'test.sqlite3')
        self.app = create_app(self.path)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def register(self, user='demo-user'):
        return self.client.post('/register', json={'id': user, 'password': 'test-password'})

    def test_account_and_route_survive_restart(self):
        self.assertEqual(self.register().status_code, 201)
        response = self.client.post('/submit', json=MEMPHIS_TRIP)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['route']['user_id'], 'demo-user')
        restarted = create_app(self.path).test_client()
        self.assertEqual(restarted.post('/login', json={'id': 'demo-user', 'password': 'test-password'}).status_code, 200)
        self.assertEqual(len(restarted.get('/routes').json['routes']), 1)
        corridor = restarted.get('/demand').json['corridors'][0]
        self.assertEqual(corridor['id'], response.json['corridorId'])
        self.assertEqual(corridor['realSupporters'], 1)
        self.assertTrue(corridor['supportedByMe'])

    def test_ownership_logout_and_password(self):
        self.assertEqual(self.client.post('/submit', json={}).status_code, 401)
        self.register()
        self.client.post('/submit', json={'id': 'someone-else', 'start_lat': 35, 'start_lng': -90, 'end_lat': 35.2, 'end_lng': -89.9})
        self.assertEqual(self.client.get('/routes').json['routes'][0]['user_id'], 'demo-user')
        self.client.post('/logout')
        self.assertEqual(self.client.get('/routes').status_code, 401)
        self.assertEqual(self.client.post('/login', json={'id': 'demo-user', 'password': 'wrong'}).status_code, 401)
        self.register('another-user')
        self.assertEqual(self.client.get('/routes').json['routes'], [])

    def test_memphis_bounds_and_minimum_trip_distance(self):
        self.register()
        for field, value in [('start_lat', 34.849), ('end_lat', 35.401),
                             ('start_lng', -90.301), ('end_lng', -89.599)]:
            with self.subTest(field=field):
                response = self.client.post('/submit', json={**MEMPHIS_TRIP, field: value})
                self.assertEqual(response.status_code, 400)
                self.assertIn('Memphis', response.json['message'])
        for trip in [dict(start_lat=35.1, start_lng=-90, end_lat=35.1, end_lng=-90),
                     dict(start_lat=35.1, start_lng=-90, end_lat=35.1005, end_lng=-90)]:
            response = self.client.post('/submit', json=trip)
            self.assertEqual(response.status_code, 400)
            self.assertIn('150 meters', response.json['message'])
        # The bounding box itself is inclusive; corner coordinates are valid.
        self.assertEqual(self.client.post('/submit', json={
            'start_lat': 34.85, 'start_lng': -90.3, 'end_lat': 35.4, 'end_lng': -89.6,
        }).status_code, 201)
        self.assertEqual(len(self.client.get('/routes').json['routes']), 1)

    def test_invalid_input_and_duplicate_user(self):
        self.register()
        self.assertEqual(self.register().status_code, 409)
        for value in [None, True, '35', 91, float('nan'), float('inf')]:
            self.assertEqual(self.client.post('/submit', json={'start_lat': value, 'start_lng': -90, 'end_lat': 35, 'end_lng': -90}).status_code, 400)
        self.assertEqual(self.client.post('/submit', json=['invalid']).status_code, 400)
        self.assertEqual(self.client.get('/routes').json['routes'], [])

    def test_nearby_and_reverse_requests_count_residents_once(self):
        self.register()
        original = self.client.post('/submit', json=MEMPHIS_TRIP).json
        reverse = self.client.post('/submit', json={
            'start_lat': 35.1182, 'start_lng': -89.9368,
            'end_lat': 35.1497, 'end_lng': -90.0488,
        }).json
        self.assertEqual(original['corridorId'], reverse['corridorId'])
        own = self.client.get('/demand').json
        self.assertEqual(own['totals'], {'supporters': 1, 'corridors': 1, 'ready': 0})
        self.assertTrue(own['corridors'][0]['supportedByMe'])
        self.assertEqual(len(self.client.get('/routes').json['routes']), 2)
        self.register('another-user')
        self.assertFalse(self.client.get('/demand').json['corridors'][0]['supportedByMe'])
        self.client.post('/submit', json=MEMPHIS_TRIP)
        shared = self.client.get('/demand').json['corridors'][0]
        self.assertEqual(shared['supporters'], 2)
        self.assertEqual(shared['realSupporters'], 2)
        self.assertEqual(shared['exampleSupporters'], 0)
        self.assertEqual(shared['progress'], 2)
        self.assertEqual(shared['stage'], 'gathering')
        self.assertTrue(shared['supportedByMe'])

    def test_public_demand_only_shares_coarse_areas(self):
        self.register()
        self.client.post('/submit', json=MEMPHIS_TRIP)
        self.client.post('/logout')
        response = self.client.get('/demand')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('demo-user', response.get_data(as_text=True))
        corridor = response.json['corridors'][0]
        self.assertFalse(corridor['supportedByMe'])
        self.assertEqual(set(corridor), {'id', 'name', 'origin', 'destination', 'supporters',
                                        'realSupporters', 'exampleSupporters', 'stage',
                                        'progress', 'supportedByMe'})
        for area in (corridor['origin'], corridor['destination']):
            self.assertEqual(set(area), {'lat', 'lng', 'label'})
            self.assertNotIn(area['lat'], (MEMPHIS_TRIP['start_lat'], MEMPHIS_TRIP['end_lat']))
            self.assertNotIn(area['lng'], (MEMPHIS_TRIP['start_lng'], MEMPHIS_TRIP['end_lng']))
        self.assertEqual(corridor['origin']['label'], 'Downtown')
        self.assertEqual(corridor['destination']['label'], 'University District')
        self.assertEqual(self.client.get('/routes').status_code, 401)

    def test_examples_are_optional_and_never_persisted(self):
        empty = self.client.get('/demand').json
        self.assertFalse(empty['includesExamples'])
        self.assertEqual(empty['corridors'], [])
        examples = self.client.get('/demand?examples=1').json
        self.assertTrue(examples['includesExamples'])
        self.assertEqual(examples['threshold'], 100)
        self.assertEqual(examples['totals'], {'supporters': 367, 'corridors': 6, 'ready': 1})
        self.assertEqual([item['supporters'] for item in examples['corridors']], [128, 86, 64, 43, 29, 17])
        self.assertEqual(examples['corridors'][0]['progress'], 100)
        self.assertEqual(examples['corridors'][0]['stage'], 'review')
        self.assertTrue(all(item['realSupporters'] == 0 and not item['supportedByMe'] for item in examples['corridors']))
        self.assertEqual(self.client.get('/demand?examples=0').json['corridors'], [])
        self.assertEqual(self.client.get('/demand?examples=true').json['corridors'], [])
        self.register()
        self.assertEqual(self.client.get('/routes').json['routes'], [])
        submission = self.client.post('/submit', json=MEMPHIS_TRIP).json
        self.client.post('/submit', json=MEMPHIS_TRIP)
        updated = self.client.get('/demand?examples=1').json
        corridor = next(item for item in updated['corridors'] if item['id'] == submission['corridorId'])
        self.assertEqual((corridor['supporters'], corridor['realSupporters'], corridor['exampleSupporters']), (87, 1, 86))
        self.assertEqual(self.client.get('/demand').json['totals']['supporters'], 1)
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM routes').fetchone()[0], 2)

    def test_real_threshold_and_totals_count_support_per_corridor(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executemany('INSERT INTO users VALUES (?, ?)', [(f'resident-{i}', 'fixture') for i in range(100)])
            db.executemany('INSERT INTO routes (user_id, start_lat, start_lng, end_lat, end_lng) VALUES (?, ?, ?, ?, ?)',
                           [(f'resident-{i}', *MEMPHIS_TRIP.values()) for i in range(100)])
            # One resident can support another corridor, but duplicating an
            # existing request must not add another unit of support there.
            db.execute('INSERT INTO routes (user_id, start_lat, start_lng, end_lat, end_lng) VALUES (?, ?, ?, ?, ?)',
                       ('resident-0', *MEMPHIS_TRIP.values()))
            db.execute('INSERT INTO routes (user_id, start_lat, start_lng, end_lat, end_lng) VALUES (?, ?, ?, ?, ?)',
                       ('resident-0', 35.036, -90.025, 35.142, -90.021))
        demand = self.client.get('/demand').json
        self.assertEqual(demand['totals'], {'supporters': 101, 'corridors': 2, 'ready': 1})
        self.assertEqual(demand['corridors'][0]['supporters'], 100)
        self.assertEqual(demand['corridors'][0]['stage'], 'review')
        self.assertEqual(demand['corridors'][0]['progress'], 100)

    def test_legacy_non_memphis_requests_stay_private(self):
        self.register()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT INTO routes (user_id, start_lat, start_lng, end_lat, end_lng) VALUES (?, ?, ?, ?, ?)',
                       ('demo-user', 0, 0, 35.1, -90))
        self.assertEqual(len(self.client.get('/routes').json['routes']), 1)
        self.assertEqual(self.client.get('/demand').json['corridors'], [])


if __name__ == '__main__':
    unittest.main()
