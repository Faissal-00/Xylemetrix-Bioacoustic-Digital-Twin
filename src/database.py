import sqlite3
import time

# 👇 Changed the name slightly so it generates a fresh database with the new column
DB_NAME = "plantpulse_macro_history.db"

def init_db():
    """Creates the database and table if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analysis_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            field_id TEXT, -- 👇 NEW COLUMN ADDED HERE
            filename TEXT,
            overall_status TEXT,
            empty_pot_count INTEGER,
            tomato_cut_count INTEGER,
            tomato_dry_count INTEGER,
            inference_time_ms INTEGER,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()

# 👇 Added field_id as the first parameter
def log_prediction(field_id, filename, overall_status, empty_pot_count, tomato_cut_count, tomato_dry_count, inference_time_ms, notes=""):
    """Inserts a new analysis result into the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 👇 Updated the SQL INSERT command to include the field_id
    cursor.execute('''
        INSERT INTO analysis_logs (field_id, filename, overall_status, empty_pot_count, tomato_cut_count, tomato_dry_count, inference_time_ms, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (field_id, filename, overall_status, empty_pot_count, tomato_cut_count, tomato_dry_count, inference_time_ms, notes))
    conn.commit()
    conn.close()

def get_history():
    """Fetches the latest 50 records for the dashboard UI."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM analysis_logs ORDER BY timestamp DESC LIMIT 50')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_record(record_id):
    """Deletes a specific analysis log by ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM analysis_logs WHERE id = ?', (record_id,))
    conn.commit()
    conn.close()

def clear_all_history():
    """Wipes the entire history database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM analysis_logs')
    conn.commit()
    conn.close()