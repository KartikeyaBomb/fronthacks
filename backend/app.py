from flask import Flask, request, jsonify
from flask_cors import CORS
from pyairtable import Table
from pyairtable.formulas import match

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": r"https://*.vercel.app"}})  # Allow CORS for specified domain


# Initialize Airtable Table
locations_table = Table(AIRTABLE_API_KEY, BASE_ID, TABLE_NAME_LOCATIONS)


@app.route('/register', methods=['POST'])
def register():
    """
    Handles user registration by checking if the ID already exists.
    """
    user_id = request.json.get('ID')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'ID is required.'}), 400

    existing_users = locations_table.all(formula=match({"ID": user_id}))
    if existing_users:
        return jsonify({'status': 'error', 'message': 'ID already exists.'}), 409

    locations_table.create({'ID': user_id})
    return jsonify({'status': 'success', 'message': 'Registration successful!'})


@app.route('/login', methods=['POST'])
def login():
    """
    Handles user login by validating the existence of the ID.
    """
    user_id = request.json.get('id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'ID is required.'}), 400

    existing_users = locations_table.all(formula=match({"ID": user_id}))
    if existing_users:
        return jsonify({'status': 'success', 'message': 'Login successful!'})
    return jsonify({'status': 'error', 'message': 'Invalid ID'}), 401


@app.route('/submit', methods=['POST'])
def submit():
    """
    Handles location submission and adds the data to the Airtable table.
    """
    data = request.json
    user_id = data.get('id')
    start_lat, start_lng = data.get('start_lat'), data.get('start_lng')
    end_lat, end_lng = data.get('end_lat'), data.get('end_lng')

    if not all([user_id, start_lat, start_lng, end_lat, end_lng]):
        return jsonify({'status': 'error', 'message': 'All location details are required.'}), 400

    existing_users = locations_table.all(formula=match({"ID": user_id}))
    if not existing_users:
        return jsonify({'status': 'error', 'message': 'User ID not found.'}), 404

    locations_table.create({
        'ID': user_id,
        'Start Lat': start_lat,
        'Start Lng': start_lng,
        'End Lat': end_lat,
        'End Lng': end_lng,
    })
    return jsonify({'status': 'success', 'message': 'Coordinates saved successfully.'})


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000, debug=True)
