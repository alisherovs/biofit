import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_name):
        self.db_name = db_name
        self.create_tables()

    def connect(self):
        return sqlite3.connect(self.db_name)

    def create_tables(self):
        with self.connect() as conn:
            cursor = conn.cursor()
            # Users
            cursor.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id BIGINT UNIQUE,
                name TEXT, phone TEXT,
                is_approved BOOLEAN DEFAULT 0,
                is_online BOOLEAN DEFAULT 0,
                current_number TEXT,
                registered_at DATETIME
            )""")
            # Numbers
            cursor.execute("""CREATE TABLE IF NOT EXISTS numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE,
                is_used BOOLEAN DEFAULT 0,
                assigned_to BIGINT,
                taken_at DATETIME
            )""")
            # Calls
            cursor.execute("""CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_id BIGINT, phone_number TEXT, status TEXT,
                client_name TEXT, client_age INTEGER, client_height INTEGER, client_weight INTEGER,
                created_at DATETIME
            )""")
            # Settings (YANGI: Limitni saqlash uchun)
            cursor.execute("""CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )""")
            # Default limit: 20
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_limit', '20')")
            conn.commit()

    # --- SETTINGS (LIMIT) ---
    def get_limit(self):
        with self.connect() as conn:
            res = conn.execute("SELECT value FROM settings WHERE key='daily_limit'").fetchone()
            return int(res[0]) if res else 20

    def set_limit(self, limit):
        with self.connect() as conn:
            conn.execute("UPDATE settings SET value = ? WHERE key='daily_limit'", (str(limit),))

    def get_today_count(self, op_id):
        # Operator bugun nechta qo'ng'iroq qilganini sanaydi
        today = datetime.now().strftime("%Y-%m-%d")
        with self.connect() as conn:
            res = conn.execute("SELECT COUNT(*) FROM calls WHERE operator_id = ? AND created_at LIKE ?", (op_id, f"{today}%")).fetchone()
            return res[0] if res else 0

    # --- NUMBERS (YANGILANDI) ---
    def add_numbers(self, numbers_list):
        count = 0
        updated = 0
        with self.connect() as conn:
            for num in numbers_list:
                # 1. Agar raqam yo'q bo'lsa -> Qo'shamiz
                try:
                    conn.execute("INSERT INTO numbers (phone_number) VALUES (?)", (num,))
                    count += 1
                except sqlite3.IntegrityError:
                    # 2. Agar raqam bo'lsa -> Uni qayta "bo'sh" (used=0) qilamiz (RECYCLE)
                    conn.execute("UPDATE numbers SET is_used = 0, assigned_to = NULL WHERE phone_number = ?", (num,))
                    updated += 1
        return count, updated

    def get_no_answer_numbers(self):
        # Kotarmagan raqamlarni olish
        with self.connect() as conn:
            return conn.execute("SELECT phone_number FROM calls WHERE status = 'no_answer'").fetchall()

    # --- QOLGAN ESKI FUNKSIYALAR ---
    def add_user(self, telegram_id, name, phone):
        with self.connect() as conn:
            try:
                conn.execute("INSERT INTO users (telegram_id, name, phone, registered_at) VALUES (?, ?, ?, ?)", (telegram_id, name, phone, datetime.now()))
                return True
            except: return False

    def get_user(self, telegram_id):
        with self.connect() as conn: return conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    
    def get_all_users(self):
        with self.connect() as conn: return conn.execute("SELECT * FROM users").fetchall()

    def approve_user(self, telegram_id, approved=True):
        with self.connect() as conn: conn.execute("UPDATE users SET is_approved = ? WHERE telegram_id = ?", (approved, telegram_id))

    def delete_user(self, telegram_id):
        with self.connect() as conn: conn.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))

    def set_online(self, telegram_id, status: bool):
        with self.connect() as conn: conn.execute("UPDATE users SET is_online = ? WHERE telegram_id = ?", (status, telegram_id))

    def set_current_number(self, telegram_id, number):
        with self.connect() as conn: conn.execute("UPDATE users SET current_number = ? WHERE telegram_id = ?", (number, telegram_id))

    def get_free_number(self, telegram_id):
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT phone_number FROM numbers WHERE is_used = 0 LIMIT 1")
            res = cursor.fetchone()
            if res:
                phone = res[0]
                cursor.execute("UPDATE numbers SET is_used = 1, assigned_to = ?, taken_at = ? WHERE phone_number = ?", (telegram_id, datetime.now(), phone))
                conn.commit()
                return phone
            return None

    def get_all_numbers(self):
        with self.connect() as conn: return conn.execute("SELECT n.phone_number, n.is_used, u.name, n.taken_at FROM numbers n LEFT JOIN users u ON n.assigned_to = u.telegram_id").fetchall()

    def clear_numbers_and_calls(self):
        with self.connect() as conn:
            conn.execute("DELETE FROM numbers")
            conn.execute("DELETE FROM calls")
            conn.execute("UPDATE users SET current_number = NULL")

    def add_call(self, data):
        with self.connect() as conn:
            conn.execute("INSERT INTO calls (operator_id, phone_number, status, client_name, client_age, client_height, client_weight, created_at) VALUES (?,?,?,?,?,?,?,?)", 
                         (data['op_id'], data['phone'], data['status'], data.get('name'), data.get('age'), data.get('height'), data.get('weight'), datetime.now()))

    def get_calls_stats(self, start, end, operator_id=None):
        with self.connect() as conn:
            query = "SELECT c.operator_id, u.name, c.phone_number, c.status, c.client_name, c.client_age, c.client_height, c.client_weight, c.created_at FROM calls c LEFT JOIN users u ON c.operator_id = u.telegram_id WHERE c.created_at BETWEEN ? AND ?"
            params = [start, end]
            if operator_id:
                query += " AND c.operator_id = ?"
                params.append(operator_id)
            return conn.execute(query, params).fetchall()

    def get_general_stats(self):
        with self.connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            success = conn.execute("SELECT COUNT(*) FROM calls WHERE status = 'success'").fetchone()[0]
            no = conn.execute("SELECT COUNT(*) FROM calls WHERE status = 'no_answer'").fetchone()[0]
            inv = conn.execute("SELECT COUNT(*) FROM calls WHERE status = 'invalid'").fetchone()[0]
            return total, success, no, inv

    def get_operator_ranking(self):
        with self.connect() as conn:
            return conn.execute("SELECT u.name, u.telegram_id, COUNT(c.id), SUM(CASE WHEN c.status='success' THEN 1 ELSE 0 END) FROM users u LEFT JOIN calls c ON u.telegram_id = c.operator_id GROUP BY u.telegram_id ORDER BY 4 DESC").fetchall()

    def search_phone_by_digits(self, digits):
        with self.connect() as conn:
            return conn.execute("SELECT c.phone_number, u.name, c.created_at, c.status, c.client_name, c.client_age, c.client_height, c.client_weight FROM calls c LEFT JOIN users u ON c.operator_id = u.telegram_id WHERE c.phone_number LIKE ? ORDER BY c.created_at DESC", (f"%{digits}",)).fetchall()

db = Database("call_center.db")
