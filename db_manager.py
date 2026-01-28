import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_name="call_center.db"):
        self.db_name = db_name
        self.create_tables()

    def connect(self):
        return sqlite3.connect(self.db_name)

    def create_tables(self):
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # 1. USERS
            cursor.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id BIGINT UNIQUE, name TEXT, phone TEXT,
                is_approved BOOLEAN DEFAULT 0, is_online BOOLEAN DEFAULT 0,
                current_number TEXT, is_coadmin BOOLEAN DEFAULT 0,
                registered_at DATETIME
            )""")
            
            # 2. NUMBERS (Mijozlar)
            cursor.execute("""CREATE TABLE IF NOT EXISTS numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE, -- Asosiy ID
                full_name TEXT,           -- Ism
                telegram_user TEXT,       -- Telegram
                extra_info TEXT,          -- Qo'shimcha (Ota-ona)
                is_used BOOLEAN DEFAULT 0,
                assigned_to BIGINT,
                taken_at DATETIME
            )""")
            
            # 3. CALLS
            cursor.execute("""CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_id BIGINT, phone_number TEXT, status TEXT,
                client_name TEXT, client_age INTEGER, client_height INTEGER, client_weight INTEGER,
                interest TEXT, created_at DATETIME
            )""")
            
            # 4. SETTINGS
            cursor.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_limit', '20')")
            conn.commit()

    # --- SOZLAMALAR ---
    def get_limit(self):
        with self.connect() as conn:
            res = conn.execute("SELECT value FROM settings WHERE key='daily_limit'").fetchone()
            return int(res[0]) if res else 20
    def set_limit(self, limit):
        with self.connect() as conn: conn.execute("UPDATE settings SET value = ? WHERE key='daily_limit'", (str(limit),))

    def get_today_count(self, op_id):
        today = datetime.now().strftime("%Y-%m-%d")
        with self.connect() as conn:
            res = conn.execute("SELECT COUNT(*) FROM calls WHERE operator_id = ? AND created_at LIKE ?", (op_id, f"{today}%")).fetchone()
            return res[0] if res else 0
    def get_today_no_answers(self, op_id):
        today = datetime.now().strftime("%Y-%m-%d")
        with self.connect() as conn:
            return conn.execute("SELECT phone_number FROM calls WHERE operator_id = ? AND status = 'no_answer' AND created_at LIKE ?", (op_id, f"{today}%")).fetchall()

    # --- RAQAMLAR LOGIKASI ---
    def add_full_number(self, phone, name, tg, extra):
        """Exceldan olingan ma'lumotlarni saqlash"""
        with self.connect() as conn:
            try:
                conn.execute("""
                    INSERT INTO numbers (phone_number, full_name, telegram_user, extra_info) 
                    VALUES (?, ?, ?, ?)
                """, (phone, name, tg, extra))
                return True
            except sqlite3.IntegrityError:
                # Yangilash
                conn.execute("""
                    UPDATE numbers 
                    SET full_name=?, telegram_user=?, extra_info=?, is_used=0, assigned_to=NULL 
                    WHERE phone_number=?
                """, (name, tg, extra, phone))
                return "updated"

    def get_free_number_full(self, telegram_id):
        """Operatorga raqam berish"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT phone_number, full_name, telegram_user, extra_info 
                FROM numbers WHERE is_used = 0 LIMIT 1
            """)
            res = cursor.fetchone()
            if res:
                phone = res[0]
                cursor.execute("UPDATE numbers SET is_used = 1, assigned_to = ?, taken_at = ? WHERE phone_number = ?", (telegram_id, datetime.now(), phone))
                conn.commit()
                return res # (phone, name, tg, extra)
            return None

    def get_all_numbers(self):
        with self.connect() as conn: 
            return conn.execute("SELECT n.phone_number, n.is_used, u.name, n.taken_at FROM numbers n LEFT JOIN users u ON n.assigned_to = u.telegram_id").fetchall()
    def get_no_answer_numbers(self):
        with self.connect() as conn: return conn.execute("SELECT phone_number FROM calls WHERE status = 'no_answer'").fetchall()
    def clear_numbers_and_calls(self):
        with self.connect() as conn:
            conn.execute("DELETE FROM numbers"); conn.execute("DELETE FROM calls"); conn.execute("UPDATE users SET current_number = NULL")

    # --- USERS ---
    def add_user(self, telegram_id, name, phone):
        with self.connect() as conn:
            try: conn.execute("INSERT INTO users (telegram_id, name, phone, registered_at) VALUES (?, ?, ?, ?)", (telegram_id, name, phone, datetime.now())); return True
            except: return False
    def get_user(self, telegram_id):
        with self.connect() as conn: return conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    def get_all_users(self):
        with self.connect() as conn: return conn.execute("SELECT * FROM users").fetchall()
    def approve_user(self, telegram_id, approved=True):
        with self.connect() as conn: conn.execute("UPDATE users SET is_approved = ? WHERE telegram_id = ?", (approved, telegram_id))
    def make_coadmin(self, telegram_id, status=True):
        with self.connect() as conn: 
            try: conn.execute("UPDATE users SET is_coadmin = ? WHERE telegram_id = ?", (status, telegram_id))
            except: pass
    def delete_user(self, telegram_id):
        with self.connect() as conn: conn.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
    def set_online(self, telegram_id, status: bool):
        with self.connect() as conn: conn.execute("UPDATE users SET is_online = ? WHERE telegram_id = ?", (status, telegram_id))
    def set_current_number(self, telegram_id, number):
        with self.connect() as conn: conn.execute("UPDATE users SET current_number = ? WHERE telegram_id = ?", (number, telegram_id))

    # --- CALLS ---
    def add_call(self, data):
        with self.connect() as conn:
            conn.execute("INSERT INTO calls (operator_id, phone_number, status, client_name, client_age, client_height, client_weight, interest, created_at) VALUES (?,?,?,?,?,?,?,?,?)", 
                         (data['op_id'], data['phone'], data['status'], data.get('name'), data.get('age'), data.get('height'), data.get('weight'), data.get('interest'), datetime.now()))
    def get_calls_stats(self, start, end, operator_id=None):
        with self.connect() as conn:
            query = "SELECT c.operator_id, u.name, c.phone_number, c.status, c.client_name, c.client_age, c.client_height, c.client_weight, c.interest, c.created_at FROM calls c LEFT JOIN users u ON c.operator_id = u.telegram_id WHERE c.created_at BETWEEN ? AND ?"
            params = [start, end]
            if operator_id: query += " AND c.operator_id = ?"; params.append(operator_id)
            return conn.execute(query, params).fetchall()
    def get_general_stats(self):
        with self.connect() as conn:
            t = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            s = conn.execute("SELECT COUNT(*) FROM calls WHERE status = 'success'").fetchone()[0]
            n = conn.execute("SELECT COUNT(*) FROM calls WHERE status = 'no_answer'").fetchone()[0]
            i = conn.execute("SELECT COUNT(*) FROM calls WHERE status = 'invalid'").fetchone()[0]
            return t, s, n, i
    def get_operator_ranking(self):
        with self.connect() as conn: return conn.execute("SELECT u.name, u.telegram_id, COUNT(c.id), SUM(CASE WHEN c.status='success' THEN 1 ELSE 0 END) FROM users u LEFT JOIN calls c ON u.telegram_id = c.operator_id GROUP BY u.telegram_id ORDER BY 4 DESC").fetchall()
    def search_phone_by_digits(self, digits):
        with self.connect() as conn:
            return conn.execute("""
                SELECT c.phone_number, u.name, c.created_at, c.status, 
                       c.client_name, c.client_age, c.client_height, c.client_weight, 
                       c.interest, c.operator_id 
                FROM calls c 
                LEFT JOIN users u ON c.operator_id = u.telegram_id 
                WHERE c.phone_number LIKE ? 
                ORDER BY c.created_at DESC
            """, (f"%{digits}",)).fetchall()

db = Database("call_center.db")
