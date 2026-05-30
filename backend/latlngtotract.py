import sqlite3
import requests

# Define the function to fetch the census tract
def get_census_tract(lat, lon):
    base_url = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
    params = {
        "x": lon,
        "y": lat,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json"
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        geographies = data.get("result", {}).get("geographies", {})

        if "Census Tracts" in geographies:
            tract_info = geographies["Census Tracts"][0]
            return tract_info.get("GEOID")
        else:
            return "Census tract not found"

    except requests.RequestException as e:
        print(f"API request failed: {e}")
        return None

# Function to update the database with start and destination census tracts in a single table
def update_census_tracts(database_path):
    # Connect to the SQLite database
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    # Create a table for both start and end census tracts if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS census_tracts (
            id INTEGER PRIMARY KEY,
            start_census_tract TEXT,
            end_census_tract TEXT
        )
    """)

    # Fetch rows with latitude and longitude
    cursor.execute("SELECT id, latitudeStart, longitudeStart, latitudeEnd, longitudeEnd FROM locations")
    rows = cursor.fetchall()

    for row in rows:
        row_id, lat_start, lon_start, lat_end, lon_end = row
        print(f"Processing ID {row_id}")

        # Process start location
        start_census_tract = get_census_tract(lat_start, lon_start)
        if not start_census_tract:
            print(f"Failed to get start census tract for ID {row_id}")
            start_census_tract = "Not Found"

        # Process destination location
        end_census_tract = get_census_tract(lat_end, lon_end)
        if not end_census_tract:
            print(f"Failed to get end census tract for ID {row_id}")
            end_census_tract = "Not Found"

        # Insert into the census_tracts table
        cursor.execute(
            """
            INSERT OR REPLACE INTO census_tracts (id, start_census_tract, end_census_tract)
            VALUES (?, ?, ?)
            """,
            (row_id, start_census_tract, end_census_tract)
        )

        print(f"ID {row_id}: Start - {start_census_tract}, End - {end_census_tract}")

    # Commit changes and close the connection
    conn.commit()
    conn.close()
    print("Census tract updates complete.")

# Call the function to update the database
update_census_tracts("app.db")