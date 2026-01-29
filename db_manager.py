import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_file):
        self.connection = sqlite3.connect(db_file)
        self.cursor = self.connection.cursor()
        self.create_tables()

    def create_tables(self):
        # Foydalanuvchilar (Operatorlar)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                full_name TEXT,
                phone TEXT,
                is_approved BOOLEAN DEFAULT 0,
                is_online BOOLEAN DEFAULT 0,
                current_number TEXT DEFAULT NULL,
                is_coadmin BOOLEAN DEFAULT 0
            )
        """)
        # Bazadagi raqamlar (Mijozlar)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE,
                full_name TEXT,
                telegram_user TEXT,
                extra_info TEXT,
                status TEXT DEFAULT 'new',
                operator_id INTEGER DEFAULT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Qo'ng'iroqlar tarixi
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_id INTEGER,
                phone TEXT,
                status TEXT,
                client_name TEXT,
                age INTEGER,
                height INTEGER,
                weight INTEGER,
                interest TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.connection.commit()

    # --- USER METHODS ---
    def add_user(self, user_id, full_name, phone):
        try:
            self.cursor.execute("INSERT INTO users (user_id, full_name, phone) VALUES (?, ?, ?)", 
                               (user_id, full_name, phone))
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_user(self, user_id):
        return self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

    def get_all_users(self):
        return self.cursor.execute("SELECT * FROM users").fetchall()

    def approve_user(self, user_id, status):
        self.cursor.execute("UPDATE users SET is_approved = ? WHERE user_id = ?", (status, user_id))
        self.connection.commit()

    def delete_user(self, user_id):
        self.cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        self.connection.commit()

    def set_online(self, user_id, status):
        self.cursor.execute("UPDATE users SET is_online = ? WHERE user_id = ?", (status, user_id))
        self.connection.commit()

    def set_current_number(self, user_id, phone):
        self.cursor.execute("UPDATE users SET current_number = ? WHERE user_id = ?", (phone, user_id))
        self.connection.commit()

    def make_coadmin(self, user_id, status):
        self.cursor.execute("UPDATE users SET is_coadmin = ? WHERE user_id = ?", (status, user_id))
        self.connection.commit()

    # --- NUMBER METHODS ---
    def add_full_number(self, phone, name, tg, extra):
        try:
            self.cursor.execute("INSERT INTO numbers (phone, full_name, telegram_user, extra_info) VALUES (?, ?, ?, ?)",
                               (phone, name, tg, extra))
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            # Agar bor bo'lsa yangilaymiz
            self.cursor.execute("UPDATE numbers SET full_name=?, telegram_user=?, extra_info=? WHERE phone=?",
                               (name, tg, extra, phone))
            self.connection.commit()
            return "updated"

    def get_free_number_full(self, operator_id):
        # 1. Avval eski "recalled" (qayta bog'lanish) larni tekshiramiz
        res = self.cursor.execute("SELECT phone, full_name, telegram_user, extra_info FROM numbers WHERE operator_id = ? AND status = 'recalled'", (operator_id,)).fetchone()
        if res: return res
        
        # 2. Yangi raqam beramiz
        res = self.cursor.execute("SELECT phone, full_name, telegram_user, extra_info FROM numbers WHERE status = 'new' LIMIT 1").fetchone()
        if res:
            self.cursor.execute("UPDATE numbers SET status = 'process', operator_id = ?, last_updated = ? WHERE phone = ?", 
                               (operator_id, datetime.now(), res[0]))
            self.connection.commit()
        return res

    def get_all_numbers(self):
        return self.cursor.execute("SELECT phone, status, operator_id, last_updated FROM numbers").fetchall()
    
    def get_no_answer_numbers(self):
        return self.cursor.execute("SELECT phone FROM numbers WHERE status = 'no_answer'").fetchall()

    def search_phone_by_digits(self, digits):
        return self.cursor.execute(f"SELECT n.phone, u.full_name, n.last_updated, n.status, c.client_name, c.age, c.height, c.weight, c.interest, n.operator_id FROM numbers n LEFT JOIN users u ON n.operator_id = u.user_id LEFT JOIN calls c ON n.phone = c.phone WHERE n.phone LIKE '%{digits}'").fetchall()

    def clear_numbers_and_calls(self):
        self.cursor.execute("DELETE FROM numbers")
        self.cursor.execute("DELETE FROM calls")
        self.cursor.execute("UPDATE users SET current_number = NULL")
        self.connection.commit()

    # --- CALL METHODS & STATS ---
    def add_call(self, data):
        self.cursor.execute("""
            INSERT INTO calls (operator_id, phone, status, client_name, age, height, weight, interest, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data.get('op_id'), data.get('phone'), data.get('status'), data.get('name'), data.get('age'), data.get('height'), data.get('weight'), data.get('interest'), datetime.now()))
        
        # Raqam statusini yangilash
        new_status = data.get('status')
        self.cursor.execute("UPDATE numbers SET status = ? WHERE phone = ?", (new_status, data.get('phone')))
        self.connection.commit()

    def get_limit(self):
        # Sodda limit tizimi (faylda saqlash o'rniga shu yerda qattiq kodlanadi yoki alohida table qilish mumkin)
        # Hozircha default 50 qaytaradi, admin o'zgartirishi uchun alohida table kerak bo'ladi, 
        # lekin kodni murakkablashtirmaslik uchun 100 deb turamiz.
        return 100

    def set_limit(self, limit):
        # Bu funksiya uchun alohida settings table kerak, hozircha pass
        pass

    def get_today_count(self, user_id):
        start_of_day = datetime.now().replace(hour=0, minute=0, second=0)
        return self.cursor.execute("SELECT COUNT(*) FROM calls WHERE operator_id = ? AND timestamp >= ?", (user_id, start_of_day)).fetchone()[0]

    def get_general_stats(self):
        total = self.cursor.execute("SELECT COUNT(*) FROM numbers").fetchone()[0]
        success = self.cursor.execute("SELECT COUNT(*) FROM numbers WHERE status = 'success'").fetchone()[0]
        no_ans = self.cursor.execute("SELECT COUNT(*) FROM numbers WHERE status = 'no_answer'").fetchone()[0]
        invalid = self.cursor.execute("SELECT COUNT(*) FROM numbers WHERE status = 'invalid'").fetchone()[0]
        return total, success, no_ans, invalid

    def get_operator_ranking(self):
        return self.cursor.execute("""
            SELECT u.full_name, u.phone, u.user_id, COUNT(c.id) as count 
            FROM users u LEFT JOIN calls c ON u.user_id = c.operator_id 
            WHERE c.status = 'success' 
            GROUP BY u.user_id ORDER BY count DESC
        """).fetchall()

    def get_calls_stats(self, start_date, end_date, op_id=None):
        query = """
            SELECT c.operator_id, u.full_name, c.phone, c.status, c.client_name, c.age, c.height, c.weight, c.interest, c.timestamp
            FROM calls c LEFT JOIN users u ON c.operator_id = u.user_id
            WHERE c.timestamp BETWEEN ? AND ?
        """
        params = [start_date, end_date]
        if op_id:
            query += " AND c.operator_id = ?"
            params.append(op_id)
        return self.cursor.execute(query, params).fetchall()

db = Database("bot_database.db")
