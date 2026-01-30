import sqlite3
import logging
from datetime import datetime

# Loglarni sozlash (Xatolarni terminalda ko'rish uchun)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Database:
    def __init__(self, db_name="call_center.db"):
        self.db_name = db_name
        self.create_tables()

    def connect(self):
        """Bazaga ulanish uchun yordamchi funksiya"""
        try:
            return sqlite3.connect(self.db_name)
        except sqlite3.Error as e:
            logging.error(f"Bazaga ulanishda xatolik: {e}")
            return None

    def create_tables(self):
        """Jadvallarni yaratish va boshlang'ich sozlamalarni kiritish"""
        try:
            with self.connect() as conn:
                cursor = conn.cursor()
                
                # 1. USERS (Operatorlar jadvali)
                cursor.execute("""CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id BIGINT UNIQUE, 
                    name TEXT, 
                    phone TEXT,
                    is_approved BOOLEAN DEFAULT 0, 
                    is_online BOOLEAN DEFAULT 0,
                    current_number TEXT DEFAULT NULL, 
                    is_coadmin BOOLEAN DEFAULT 0,
                    registered_at DATETIME
                )""")
                
                # 2. NUMBERS (Mijozlar bazasi)
                # status turlari: new, process, success, recalled, no_answer, invalid
                cursor.execute("""CREATE TABLE IF NOT EXISTS numbers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_number TEXT UNIQUE,
                    full_name TEXT,
                    telegram_user TEXT,
                    extra_info TEXT,
                    is_used BOOLEAN DEFAULT 0,
                    assigned_to BIGINT DEFAULT NULL,
                    taken_at DATETIME DEFAULT NULL,
                    status TEXT DEFAULT 'new'
                )""")
                
                # 3. CALLS (Qo'ng'iroqlar tarixi - Statistika va hisobotlar uchun)
                cursor.execute("""CREATE TABLE IF NOT EXISTS calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operator_id BIGINT, 
                    phone_number TEXT, 
                    status TEXT,
                    client_name TEXT, 
                    client_age INTEGER, 
                    client_height INTEGER, 
                    client_weight INTEGER,
                    interest TEXT, 
                    created_at DATETIME
                )""")
                
                # 4. SETTINGS (Tizim sozlamalari, masalan kunlik limit)
                cursor.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
                
                # Boshlang'ich limitni o'rnatish (agar yo'q bo'lsa)
                cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_limit', '50')")
                
                conn.commit()
                logging.info("Jadvallar tekshirildi va tayyorlandi.")
        except sqlite3.Error as e:
            logging.error(f"Jadval yaratishda xatolik: {e}")

    # ================== SOZLAMALAR (LIMIT) ==================
    
    def get_limit(self):
        """Kunlik limitni olish"""
        try:
            with self.connect() as conn:
                res = conn.execute("SELECT value FROM settings WHERE key='daily_limit'").fetchone()
                return int(res[0]) if res else 50
        except Exception as e:
            logging.error(f"Limitni olishda xatolik: {e}")
            return 50

    def set_limit(self, limit):
        """Kunlik limitni o'zgartirish"""
        with self.connect() as conn: 
            conn.execute("UPDATE settings SET value = ? WHERE key='daily_limit'", (str(limit),))
            logging.info(f"Yangi limit o'rnatildi: {limit}")

    # ================== STATISTIKA VA TEKSHIRUVLAR ==================
    
    def get_today_count(self, op_id):
        """Operatorning bugungi qo'ng'iroqlari soni"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            with self.connect() as conn:
                res = conn.execute("SELECT COUNT(*) FROM calls WHERE operator_id = ? AND created_at LIKE ?", (op_id, f"{today}%")).fetchone()
                return res[0] if res else 0
        except Exception:
            return 0

    def get_today_no_answers(self, op_id):
        """Bugungi 'ko'tarmadi' raqamlar ro'yxati"""
        today = datetime.now().strftime("%Y-%m-%d")
        with self.connect() as conn:
            return conn.execute("SELECT phone_number FROM calls WHERE operator_id = ? AND status = 'no_answer' AND created_at LIKE ?", (op_id, f"{today}%")).fetchall()

    def get_number_details(self, phone):
        """Raqam bo'yicha barcha ma'lumotlarni olish (qayta ishlash uchun)"""
        with self.connect() as conn:
            return conn.execute("SELECT phone_number, full_name, telegram_user, extra_info FROM numbers WHERE phone_number = ?", (phone,)).fetchone()

    # ================== RAQAMLAR LOGIKASI ==================
    
    def add_full_number(self, phone, name, tg, extra):
        """Exceldan import qilish yoki yangi raqam qo'shish"""
        with self.connect() as conn:
            try:
                conn.execute("""
                    INSERT INTO numbers (phone_number, full_name, telegram_user, extra_info, is_used, status) 
                    VALUES (?, ?, ?, ?, 0, 'new')
                """, (phone, name, tg, extra))
                return True
            except sqlite3.IntegrityError:
                # Agar raqam mavjud bo'lsa, uni yangilaymiz (Reset qilamiz)
                conn.execute("""
                    UPDATE numbers 
                    SET full_name=?, telegram_user=?, extra_info=?, is_used=0, assigned_to=NULL, status='new'
                    WHERE phone_number=?
                """, (name, tg, extra, phone))
                return "updated"
            except Exception as e:
                logging.error(f"Raqam qo'shishda xatolik: {e}")
                return False

    def get_free_number_full(self, telegram_id):
        """Operatorga raqam berish mantig'i (Eng muhim qism)"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # 1. Qayta qo'ng'iroq (Recalled) - Eng yuqori prioritet
            # Bu operator oldin gaplashib, "qayta chiqaman" degan raqamlar
            res = cursor.execute("""
                SELECT phone_number, full_name, telegram_user, extra_info 
                FROM numbers 
                WHERE assigned_to = ? AND status = 'recalled'
                LIMIT 1
            """, (telegram_id,)).fetchone()
            
            if res: 
                logging.info(f"Operator {telegram_id} ga qayta qo'ng'iroq berildi: {res[0]}")
                return res
            
            # 2. Yangi raqam (Hali hech kim ishlatmagan)
            res = cursor.execute("""
                SELECT phone_number, full_name, telegram_user, extra_info 
                FROM numbers 
                WHERE is_used = 0 
                LIMIT 1
            """).fetchone()
            
            if res:
                phone = res[0]
                # Raqamni shu operatorga biriktiramiz va vaqtini belgilaymiz
                cursor.execute("""
                    UPDATE numbers 
                    SET is_used = 1, assigned_to = ?, taken_at = ?, status = 'process' 
                    WHERE phone_number = ?
                """, (telegram_id, datetime.now(), phone))
                conn.commit()
                logging.info(f"Operator {telegram_id} ga yangi raqam berildi: {phone}")
                return res
            
            return None # Baza bo'sh

    def get_all_numbers(self):
        """Admin uchun barcha raqamlar ro'yxati"""
        with self.connect() as conn: 
            return conn.execute("SELECT n.phone_number, n.is_used, u.name, n.taken_at FROM numbers n LEFT JOIN users u ON n.assigned_to = u.telegram_id").fetchall()
    
    def get_no_answer_numbers(self):
        """Javob bermaganlar ro'yxati"""
        with self.connect() as conn: 
            return conn.execute("SELECT phone_number FROM calls WHERE status = 'no_answer'").fetchall()
    
    def clear_numbers_and_calls(self):
        """Bazani tozalash (Faqat Admin uchun)"""
        try:
            with self.connect() as conn:
                conn.execute("DELETE FROM numbers")
                conn.execute("DELETE FROM calls")
                conn.execute("UPDATE users SET current_number = NULL")
                logging.warning("Barcha raqamlar va tarix tozalandi!")
        except Exception as e:
            logging.error(f"Tozalashda xatolik: {e}")

    # ================== USERS (FOYDALANUVCHILAR) ==================
    
    def add_user(self, telegram_id, name, phone):
        """Yangi operator qo'shish"""
        with self.connect() as conn:
            try: 
                conn.execute("INSERT INTO users (telegram_id, name, phone, registered_at) VALUES (?, ?, ?, ?)", (telegram_id, name, phone, datetime.now()))
                logging.info(f"Yangi user qo'shildi: {name} ({telegram_id})")
                return True
            except sqlite3.IntegrityError:
                return False # User allaqachon bor

    def get_user(self, telegram_id):
        """User ma'lumotlarini olish"""
        with self.connect() as conn: 
            return conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    
    def get_all_users(self):
        with self.connect() as conn: 
            return conn.execute("SELECT * FROM users").fetchall()
    
    def approve_user(self, telegram_id, approved=True):
        """Operatorni tasdiqlash"""
        with self.connect() as conn: 
            conn.execute("UPDATE users SET is_approved = ? WHERE telegram_id = ?", (approved, telegram_id))
    
    def delete_user(self, telegram_id):
        """Operatorni o'chirish"""
        with self.connect() as conn: 
            conn.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
    
    def set_online(self, telegram_id, status: bool):
        """Ish vaqtini boshlash/tugatish"""
        with self.connect() as conn: 
            conn.execute("UPDATE users SET is_online = ? WHERE telegram_id = ?", (status, telegram_id))
    
    def set_current_number(self, telegram_id, number):
        """Hozirgi aktiv raqamni saqlash"""
        with self.connect() as conn: 
            conn.execute("UPDATE users SET current_number = ? WHERE telegram_id = ?", (number, telegram_id))

    def make_coadmin(self, telegram_id, status=True):
        """Co-Admin qilish"""
        with self.connect() as conn: 
            try: conn.execute("UPDATE users SET is_coadmin = ? WHERE telegram_id = ?", (status, telegram_id))
            except: pass

    # ================== CALLS (QO'NG'IROQNI SAQLASH) ==================
    
    def add_call(self, data):
        """
        Qo'ng'iroq natijasini saqlash.
        Bu funksiya 2 ta ish qiladi:
        1. Calls jadvaliga tarix yozadi.
        2. Numbers jadvalida raqam statusini yangilaydi.
        """
        with self.connect() as conn:
            try:
                conn.execute("""
                    INSERT INTO calls (operator_id, phone_number, status, client_name, client_age, client_height, client_weight, interest, created_at) 
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (data.get('op_id'), data.get('phone'), data.get('status'), data.get('name'), data.get('age'), data.get('height'), data.get('weight'), data.get('interest'), datetime.now()))
                
                conn.execute("UPDATE numbers SET status = ? WHERE phone_number = ?", (data.get('status'), data.get('phone')))
                logging.info(f"Qo'ng'iroq saqlandi: {data.get('phone')} - {data.get('status')}")
            except Exception as e:
                logging.error(f"Call saqlashda xatolik: {e}")

    def get_calls_stats(self, start, end, operator_id=None):
        """Excel hisobot uchun statistika olish"""
        with self.connect() as conn:
            query = """
                SELECT c.operator_id, u.name, c.phone_number, c.status, 
                       c.client_name, c.client_age, c.client_height, c.client_weight, 
                       c.interest, c.created_at 
                FROM calls c 
                LEFT JOIN users u ON c.operator_id = u.telegram_id 
                WHERE c.created_at BETWEEN ? AND ?
            """
            params = [start, end]
            if operator_id: 
                query += " AND c.operator_id = ?"
                params.append(operator_id)
            return conn.execute(query, params).fetchall()

    def get_general_stats(self):
        """Admin panel uchun qisqacha statistika"""
        with self.connect() as conn:
            t = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            s = conn.execute("SELECT COUNT(*) FROM calls WHERE status = 'success'").fetchone()[0]
            n = conn.execute("SELECT COUNT(*) FROM calls WHERE status = 'no_answer'").fetchone()[0]
            i = conn.execute("SELECT COUNT(*) FROM calls WHERE status = 'invalid'").fetchone()[0]
            return t, s, n, i

    def get_operator_ranking(self):
        """Operatorlar reytingi"""
        with self.connect() as conn: 
            return conn.execute("""
                SELECT u.name, u.telegram_id, COUNT(c.id), SUM(CASE WHEN c.status='success' THEN 1 ELSE 0 END) 
                FROM users u 
                LEFT JOIN calls c ON u.telegram_id = c.operator_id 
                GROUP BY u.telegram_id 
                ORDER BY 4 DESC
            """).fetchall()

    def search_phone_by_digits(self, digits):
        """Raqam qidirish"""
        with self.connect() as conn:
            return conn.execute("""
                SELECT c.phone_number, u.name, c.created_at, c.status, 
                       c.client_name, c.client_age, c.client_height, c.client_weight, 
                       c.interest, c.operator_id 
                FROM calls c 
                LEFT JOIN users u ON c.operator_id = u.telegram_id 
                WHERE c.phone_number LIKE ? 
                ORDER BY c.created_at DESC
            """, (f"%{digits}%",)).fetchall()

# Bazani ishga tushirish
db = Database("call_center.db")
