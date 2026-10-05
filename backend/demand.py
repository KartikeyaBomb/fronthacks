"""Group route requests into approximate, bidirectional Memphis corridors.

The public view exposes only grid-cell centers, never submitted coordinates or
resident IDs. Each resident contributes at most once to a corridor. A resident
may support several corridors, so totals count corridor support, not people.
Examples are illustrative counts added on read; they never create database rows.
"""
import math


MEMPHIS_BOUNDS = (34.85, 35.4, -90.3, -89.6)
LAT_CELL_SIZE = 0.009
LNG_CELL_SIZE = 0.011
REVIEW_THRESHOLD = 100
MIN_TRIP_METERS = 150

# Approximate neighborhood anchors for readable demonstration labels. These do
# not describe official neighborhood boundaries, stops, or existing bus routes.
AREAS = {
    'Downtown': (35.1495, -90.0490),
    'Medical District': (35.142, -90.021),
    'Midtown': (35.136, -89.981),
    'Binghampton': (35.149, -89.960),
    'University District': (35.118, -89.937),
    'South Memphis': (35.095, -90.043),
    'Orange Mound': (35.109, -89.972),
    'Whitehaven': (35.036, -90.025),
    'Airport area': (35.047, -89.976),
    'Frayser': (35.214, -90.007),
    'Raleigh': (35.223, -89.921),
    'East Memphis': (35.125, -89.874),
    'Hickory Hill': (35.064, -89.865),
}

EXAMPLE_CORRIDORS = (
    ('Whitehaven', 'Medical District', 128),
    ('Downtown', 'University District', 86),
    ('Frayser', 'Downtown', 64),
    ('Orange Mound', 'East Memphis', 43),
    ('Raleigh', 'Medical District', 29),
    ('Hickory Hill', 'University District', 17),
)


def distance_meters(start, end):
    lat1, lng1 = map(math.radians, start)
    lat2, lng2 = map(math.radians, end)
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(min(1, a)))


def in_memphis(lat, lng):
    south, north, west, east = MEMPHIS_BOUNDS
    return south <= lat <= north and west <= lng <= east


def cell_for(lat, lng):
    south, _, west, _ = MEMPHIS_BOUNDS
    # Decimal grid edges can land a few machine-epsilon steps below an integer.
    # Rounding that calculation keeps an exact edge in its intended cell.
    return (math.floor(round((lat - south) / LAT_CELL_SIZE, 10)),
            math.floor(round((lng - west) / LNG_CELL_SIZE, 10)))


def corridor_key(start_lat, start_lng, end_lat, end_lng):
    return tuple(sorted((cell_for(start_lat, start_lng), cell_for(end_lat, end_lng))))


def corridor_id(key):
    return '--'.join(f'{row}_{column}' for row, column in key)


def corridor_id_for(start_lat, start_lng, end_lat, end_lng):
    return corridor_id(corridor_key(start_lat, start_lng, end_lat, end_lng))


def area_for(cell):
    south, north, west, east = MEMPHIS_BOUNDS
    lower_lat = south + cell[0] * LAT_CELL_SIZE
    lower_lng = west + cell[1] * LNG_CELL_SIZE
    lat = round((lower_lat + min(lower_lat + LAT_CELL_SIZE, north)) / 2, 6)
    lng = round((lower_lng + min(lower_lng + LNG_CELL_SIZE, east)) / 2, 6)
    nearest = min(AREAS, key=lambda name: distance_meters((lat, lng), AREAS[name]))
    distance = distance_meters((lat, lng), AREAS[nearest])
    if distance <= 1800:
        label = nearest
    elif distance <= 5000:
        label = f'Near {nearest}'
    else:
        label = f'Memphis area {cell[0]} / {cell[1]}'
    return {'lat': lat, 'lng': lng, 'label': label}


def aggregate_demand(rows, user_id=None, include_examples=False):
    supporters = {}
    examples = {}
    for row in rows:
        values = tuple(row[field] for field in ('start_lat', 'start_lng', 'end_lat', 'end_lng'))
        # Older versions accepted points anywhere. Keep their private history,
        # but exclude those records from the Memphis community visualization.
        if not in_memphis(*values[:2]) or not in_memphis(*values[2:]):
            continue
        if distance_meters(values[:2], values[2:]) < MIN_TRIP_METERS:
            continue
        key = corridor_key(*values)
        supporters.setdefault(key, set()).add(row['user_id'])

    if include_examples:
        for start_name, end_name, count in EXAMPLE_CORRIDORS:
            key = corridor_key(*AREAS[start_name], *AREAS[end_name])
            examples[key] = examples.get(key, 0) + count

    corridors = []
    for key in supporters.keys() | examples.keys():
        residents = supporters.get(key, set())
        example_count = examples.get(key, 0)
        count = len(residents) + example_count
        # Alphabetical labels give a stable, readable bidirectional name while
        # the ID depends only on grid cells.
        origin, destination = sorted((area_for(cell) for cell in key), key=lambda area: (area['label'], area['lat'], area['lng']))
        name = (f"{origin['label']} local connections" if origin['label'] == destination['label']
                else f"{origin['label']} ↔ {destination['label']}")
        corridors.append({
            'id': corridor_id(key),
            'name': name,
            'origin': origin,
            'destination': destination,
            'supporters': count,
            'realSupporters': len(residents),
            'exampleSupporters': example_count,
            'stage': 'review' if count >= REVIEW_THRESHOLD else 'gathering',
            'progress': min(100, round(count / REVIEW_THRESHOLD * 100)),
            'supportedByMe': user_id is not None and user_id in residents,
        })
    corridors.sort(key=lambda corridor: (-corridor['supporters'], corridor['id']))
    return {
        'corridors': corridors,
        'threshold': REVIEW_THRESHOLD,
        'totals': {
            'supporters': sum(corridor['supporters'] for corridor in corridors),
            'corridors': len(corridors),
            'ready': sum(corridor['stage'] == 'review' for corridor in corridors),
        },
        'includesExamples': include_examples,
    }
