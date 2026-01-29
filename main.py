import logging
import asyncio
import os
import re
from datetime import datetime, timedelta

# --- AIOGRAM 2.x KUTUBXONALARI ---
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, 
                          ReplyKeyboardRemove, InlineKeyboardMarkup, 
                          InlineKeyboardButton, InputFile)

from openpyxl import Workbook, load_workbook

# BAZA BILAN ALOQA
try:
    from db_manager import db
except ImportError:
    print("XATO: db_manager.py topilmadi!")
    exit()

# --- SOZLAMALAR ---
# Tokeningizni shu yerga qo'ying
TOKEN = "8143822107:AAFgSsJMeJ9SGdf1dQflBnExlvnsBIfRdzs"
ADMIN_IDS = [7044905076, 6134534264]  # Admin ID
ADMIN_PASSWORD = "1122"
COADMIN_PASSWORD = "3344"

# --- STATES (HOLATLAR) ---
class Reg(StatesGroup):
    name = State()

class AdminSt(StatesGroup):
    password = State()
    add_nums = State()
    set_limit = State()

class CoAdminSt(StatesGroup):
    password = State()

class Call(StatesGroup):
    waiting_for_action = State()
    phone = State()
    status = State()
    name = State()
    age = State()
    height = State()
    weight = State()
    interest = State()

class ManualEntry(StatesGroup):
    phone = State()
    action = State()

class Search(StatesGroup):
    query = State()

# BOTNI ISHGA TUSHIRISH
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ================== KLAVIATURALAR ==================
back_kb = ReplyKeyboardMarkup(resize_keyboard=True)
back_kb.add(KeyboardButton("🔙 Ortga"))

def main_kb(uid, online=False):
    st_txt = "Online ✅" if online else "Offline ❌"
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("📞 Nomer olish"), KeyboardButton("✍️ Raqam kiritish"))
    kb.add(KeyboardButton("🔍 Raqam tekshirish"))
    kb.add(KeyboardButton("🟢 Ish vaqti: " + st_txt))
    kb.add(KeyboardButton("📉 Bugungi qabul qilinmagan"))
    kb.add(KeyboardButton("📈 Shaxsiy statistikam"))
    return kb

call_action_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
call_action_kb.add(
    KeyboardButton("📞 Qo'ng'iroq qilingan (kotargan)"),
    KeyboardButton("🔄 Qayta bog'lanildi"),
    KeyboardButton("❌ Qo'ng'iroq qilinmadi"),
    KeyboardButton("🚫 Aktiv emas / noto'g'ri"),
    KeyboardButton("🔙 Ortga")
)

admin_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
admin_kb.add(KeyboardButton("📊 Umumiy statistika"), KeyboardButton("👥 Operatorlar reytingi"))
admin_kb.add(KeyboardButton("➕ Raqam(lar) qo'shish"), KeyboardButton("⚙️ Limitni sozlash"))
admin_kb.add(KeyboardButton("📉 Kotarmaganlar (Excel)"), KeyboardButton("📞 Barcha raqamlar (Excel)"))
admin_kb.add(KeyboardButton("👤 Tasdiqlangan operatorlar"), KeyboardButton("🆕 Yangi so'rovlar"))
admin_kb.add(KeyboardButton("📅 Kunlik Excel"), KeyboardButton("📅 Haftalik Excel"))
admin_kb.add(KeyboardButton("📅 Oylik Excel"), KeyboardButton("🧹 Tozalash"))
admin_kb.add(KeyboardButton("🔙 Asosiy Menyu"))

personal_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
personal_kb.add(KeyboardButton("📅 Kunlik hisobot (Excel)"), KeyboardButton("📅 Haftalik hisobot (Excel)"), KeyboardButton("🔙 Ortga"))

# ================== HANDLERS (MANTIQ) ==================

# 1. ORTGA QAYTISH
@dp.message_handler(text="🔙 Ortga", state="*")
async def global_cancel(m: types.Message, state: FSMContext):
    await state.finish()
    uid = m.from_user.id
    user = db.get_user(uid)
    if user and user[6]: db.set_current_number(uid, None)
    
    if user and user[4]:
        is_online = bool(user[5])
        await m.answer("Asosiy menyu:", reply_markup=main_kb(uid, is_online))
    else:
        await m.answer("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())

# 2. START
@dp.message_handler(commands=['start'], state="*")
async def cmd_start(m: types.Message, state: FSMContext):
    await state.finish()
    uid = m.from_user.id
    user = db.get_user(uid)
    
    if user and user[4]:
        is_online = bool(user[5])
        await m.answer("Xush kelibsiz!", reply_markup=main_kb(uid, is_online))
    elif user and not user[4]:
        await m.answer("⏳ Hisobingiz admin tasdiqlashini kutmoqda.")
    else:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(KeyboardButton("📱 Raqamni yuborish", request_contact=True))
        await m.answer("Assalomu alaykum! Ro'yxatdan o'tish uchun raqamingizni yuboring:", reply_markup=kb)

# 3. RO'YXATDAN O'TISH
@dp.message_handler(content_types=['contact'], state="*")
async def reg_contact(m: types.Message, state: FSMContext):
    phone = m.contact.phone_number
    if not phone.startswith("+"): phone = "+" + phone
    await state.update_data(phone=phone)
    await m.answer("Ism va familiyangizni kiriting:", reply_markup=back_kb)
    await Reg.name.set()

@dp.message_handler(state=Reg.name)
async def reg_name(m: types.Message, state: FSMContext):
    data = await state.get_data()
    if db.add_user(m.from_user.id, m.text, data['phone']):
        await m.answer("✅ So'rov yuborildi. Admin javobini kuting.", reply_markup=ReplyKeyboardRemove())
    else:
        await m.answer("Siz allaqachon ro'yxatdasiz.")
    await state.finish()

# 4. ISH VAQTI (ONLINE/OFFLINE)
@dp.message_handler(lambda message: message.text.startswith("🟢 Ish vaqti:"))
async def toggle_online(m: types.Message):
    uid = m.from_user.id
    user = db.get_user(uid)
    if not user or not user[4]: return await m.answer("Ruxsat yo'q.")
    
    new_status = not bool(user[5])
    db.set_online(uid, new_status)
    await m.answer("Holat o'zgardi.", reply_markup=main_kb(uid, new_status))

# 5. NOMER OLISH
@dp.message_handler(text="📞 Nomer olish")
async def get_number(m: types.Message, state: FSMContext):
    uid = m.from_user.id
    user = db.get_user(uid)
    if not user or not user[5]: return await m.answer("Avval Online bo'ling.")
    
    # Agar operatorning qo'lida tugatilmagan raqam bo'lsa
    if user[6]:
        cur_num = user[6]
        await m.answer("Sizda faol raqam bor: " + str(cur_num) + "\nNatijani tanlang:", reply_markup=call_action_kb)
        await Call.waiting_for_action.set()
        return

    # Limitni tekshirish
    limit = db.get_limit()
    count = db.get_today_count(uid)
    if count >= limit:
        await m.answer("⛔️ Kunlik limit tugadi (" + str(count) + "/" + str(limit) + ").")
        return

    # Yangi raqam olish
    data = db.get_free_number_full(uid)
    if data:
        phone, name, tg, extra = data
        db.set_current_number(uid, phone)
        
        name_val = name if name else "Topilmadi"
        tg_val = tg if tg else "Yo'q"
        extra_val = extra if extra else "Yo'q"
        
        msg = (
            "📞 <b>Yangi mijoz:</b>\n\n"
            "👤 <b>Ism:</b> " + str(name_val) + "\n"
            "📱 <b>Tel:</b> <code>" + str(phone) + "</code>\n"
            "✈️ <b>Tg:</b> " + str(tg_val) + "\n"
            "📝 <b>Info:</b> " + str(extra_val) + "\n\n"
            "<i>Qo'ng'iroq qilib, natijani tanlang:</i>"
        )
        await m.answer(msg, reply_markup=call_action_kb)
        await Call.waiting_for_action.set()
    else:
        await m.answer("⚠️ Bazada bo'sh raqam qolmadi.")

# 6. QO'LDA RAQAM KIRITISH
@dp.message_handler(text="✍️ Raqam kiritish")
async def manual_enter_start(m: types.Message):
    uid = m.from_user.id
    user = db.get_user(uid)
    if not user or not user[5]: return await m.answer("Avval Online bo'ling.")
    await m.answer("Mijoz raqamini kiriting:", reply_markup=back_kb)
    await ManualEntry.phone.set()

@dp.message_handler(state=ManualEntry.phone)
async def manual_enter_save(m: types.Message, state: FSMContext):
    phone = m.text.strip()
    if len(phone) < 7: return await m.answer("Noto'g'ri raqam.", reply_markup=back_kb)
    await state.update_data(phone=phone)
    await m.answer("Raqam: <b>" + str(phone) + "</b>\nNatijani tanlang:", reply_markup=call_action_kb)
    await ManualEntry.action.set()

# 7. QO'NG'IROQ NATIJASI
@dp.message_handler(state=[Call.waiting_for_action, ManualEntry.action])
async def log_call_result(m: types.Message, state: FSMContext):
    if m.text == "🔙 Ortga": return await global_cancel(m, state)
        
    uid = m.from_user.id
    user = db.get_user(uid)
    current_state = await state.get_state()
    
    phone = None
    if str(current_state) == "ManualEntry:action":
        d = await state.get_data()
        phone = d.get('phone')
    else:
        if not user or not user[6]: return await m.answer("Faol raqam yo'q.")
        phone = user[6]

    st_map = {
        "📞 Qo'ng'iroq qilingan (kotargan)": "success",
        "🔄 Qayta bog'lanildi": "recalled",
        "❌ Qo'ng'iroq qilinmadi": "no_answer",
        "🚫 Aktiv emas / noto'g'ri": "invalid"
    }
    
    if m.text not in st_map:
        return await m.answer("Iltimos, tugmalardan birini tanlang.")
        
    status = st_map[m.text]
    await state.update_data(phone=phone, status=status)

    if status in ["success", "recalled"]:
        await m.answer("Mijoz ismi:", reply_markup=back_kb)
        await Call.name.set()
    else:
        db.add_call({'op_id': uid, 'phone': phone, 'status': status})
        if user and user[6] == phone: db.set_current_number(uid, None)
        await state.finish()
        await m.answer("✅ Natija saqlandi!", reply_markup=main_kb(uid, True))

# 8. ANKETA TO'LDIRISH
@dp.message_handler(state=Call.name)
async def c_name(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Yosh:", reply_markup=back_kb)
    await Call.age.set()

@dp.message_handler(state=Call.age)
async def c_age(m: types.Message, state: FSMContext):
    val = int(m.text) if m.text.isdigit() else 0
    await state.update_data(age=val)
    await m.answer("Bo'y:", reply_markup=back_kb)
    await Call.height.set()

@dp.message_handler(state=Call.height)
async def c_height(m: types.Message, state: FSMContext):
    val = int(m.text) if m.text.isdigit() else 0
    await state.update_data(height=val)
    await m.answer("Vazn:", reply_markup=back_kb)
    await Call.weight.set()

@dp.message_handler(state=Call.weight)
async def c_weight(m: types.Message, state: FSMContext):
    val = int(m.text) if m.text.isdigit() else 0
    await state.update_data(weight=val)
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Ha (Qiziqdi)", callback_data="int_ha"), 
           InlineKeyboardButton("❌ Yo'q", callback_data="int_yoq"))
    
    await m.answer("Mijoz qiziqdimi?", reply_markup=kb)
    await Call.interest.set()

@dp.callback_query_handler(state=Call.interest)
async def c_interest(c: types.CallbackQuery, state: FSMContext):
    ans = "Ha" if c.data == "int_ha" else "Yo'q"
    d = await state.get_data()
    uid = c.from_user.id
    
    db.add_call({
        'op_id': uid, 'phone': d['phone'], 'status': d['status'],
        'name': d.get('name'), 'age': d.get('age'),
        'height': d.get('height'), 'weight': d.get('weight'), 'interest': ans
    })
    
    user = db.get_user(uid)
    if user and user[6] == d['phone']: db.set_current_number(uid, None)
    await state.finish()
    await c.message.edit_text("Qiziqish: " + str(ans))
    await c.message.answer("✅ Saqlandi!", reply_markup=main_kb(uid, True))

# 9. ADMIN PANEL
@dp.message_handler(commands=['admin'], state="*")
async def admin_ent(m: types.Message):
    if m.from_user.id in ADMIN_IDS:
        await m.answer("Parol:", reply_markup=back_kb)
        await AdminSt.password.set()

@dp.message_handler(state=AdminSt.password)
async def admin_chk(m: types.Message, state: FSMContext):
    if m.text == ADMIN_PASSWORD:
        await m.answer("Admin Panel", reply_markup=admin_kb)
        await state.finish()
    else:
        await m.answer("Xato.")

# 10. RAQAM YUKLASH (EXCEL)
@dp.message_handler(text="➕ Raqam(lar) qo'shish")
async def adm_add(m: types.Message):
    if m.from_user.id not in ADMIN_IDS: return
    await m.answer("Excel fayl (.xlsx) yuboring:", reply_markup=back_kb)
    await AdminSt.add_nums.set()

@dp.message_handler(content_types=['document'], state=AdminSt.add_nums)
async def adm_upload_excel(m: types.Message, state: FSMContext):
    if not m.document.file_name.endswith('.xlsx'):
        return await m.answer("Faqat .xlsx fayl yuboring!")
    
    destination = "import_" + str(m.from_user.id) + ".xlsx"
    await m.document.download(destination_file=destination)
    
    added, updated = 0, 0
    try:
        wb = load_workbook(destination, data_only=True)
        ws = wb.active
        
        # Header qidirish
        header_row_index = 1
        col_indices = {}
        found_header = False
        
        for r_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=15, values_only=True), start=1):
            row_str = [str(c).lower() if c else "" for c in row]
            if any("ismingizni_yozing" in s for s in row_str):
                header_row_index = r_idx
                found_header = True
                for c_idx, cell_val in enumerate(row_str):
                    if "ismingizni_yozing" in cell_val: col_indices['name'] = c_idx
                    elif "telefon_raqamingizni" in cell_val: col_indices['phone'] = c_idx
                    elif "telegram" in cell_val: col_indices['tg'] = c_idx
                    elif "mahsulot_uchun" in cell_val: col_indices['extra'] = c_idx
                break
        
        if not found_header:
            await m.answer("⚠️ 'ismingizni_yozing' deb boshlanuvchi qator topilmadi!")
            return

        for row in ws.iter_rows(min_row=header_row_index + 1, values_only=True):
            if not row: continue
            def get_val(key):
                if key in col_indices and col_indices[key] < len(row):
                    val = row[col_indices[key]]
                    return str(val).strip() if val else ""
                return ""
            name = get_val('name')
            raw_phone = get_val('phone')
            tg = get_val('tg')
            extra = get_val('extra')
            
            phone = re.sub(r'[^\d+]', '', raw_phone)
            if len(phone) < 7: continue
            
            res = db.add_full_number(phone, name, tg, extra)
            if res == True: added += 1
            elif res == "updated": updated += 1
            
        await m.answer("✅ Yuklandi!\n🆕 Qo'shildi: " + str(added) + "\n♻️ Yangilandi: " + str(updated), reply_markup=admin_kb)
    except Exception as e:
        await m.answer("Xatolik: " + str(e))
    finally:
        if os.path.exists(destination): os.remove(destination)
    await state.finish()

# 11. STATISTIKA VA EXCEL
@dp.message_handler(text="📊 Umumiy statistika")
async def adm_stats(m: types.Message):
    if m.from_user.id not in ADMIN_IDS: return
    t, s, n, i = db.get_general_stats()
    msg = "<b>📊 Statistika</b>\n📞 Jami: " + str(t) + "\n✅ Kotargan: " + str(s) + "\n❌ Yo'q: " + str(n) + "\n🚫 Yaroqsiz: " + str(i)
    await m.answer(msg)

async def generate_excel(m, period, op_id):
    now = datetime.now()
    if period == "kunlik": 
        s = now.replace(hour=0, minute=0, second=0)
        e = now + timedelta(days=1)
    elif period == "haftalik": 
        s = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
        e = s + timedelta(days=7)
    elif period == "oylik": 
        s = now.replace(day=1, hour=0, minute=0, second=0)
        e = (s.replace(month=s.month+1) if s.month < 12 else s.replace(year=s.year+1, month=1))
    
    rows = db.get_calls_stats(s, e, op_id)
    if not rows: return await m.answer("Ma'lumot topilmadi.")
    
    wb = Workbook(); ws = wb.active
    ws.append(["Op ID", "Op", "Tel", "Status", "Mijoz", "Yosh", "Bo'y", "Vazn", "Qiziqish", "Vaqt"])
    for r in rows: ws.append(list(r))
    
    fn = "Rep_" + str(period) + ".xlsx"
    wb.save(fn)
    await m.answer_document(InputFile(fn))
    if os.path.exists(fn): os.remove(fn)

@dp.message_handler(text=["📅 Kunlik Excel", "📅 Haftalik Excel", "📅 Oylik Excel"])
async def adm_exc(m: types.Message):
    if m.from_user.id in ADMIN_IDS:
        p = "kunlik" if "Kunlik" in m.text else "haftalik" if "Haftalik" in m.text else "oylik"
        await generate_excel(m, p, None)

@dp.message_handler(text="📉 Kotarmaganlar (Excel)")
async def adm_noans(m: types.Message):
    if m.from_user.id not in ADMIN_IDS: return
    data = db.get_no_answer_numbers()
    wb = Workbook(); ws = wb.active; ws.append(["Tel"])
    for r in data: ws.append(list(r))
    fn = "NoAns.xlsx"; wb.save(fn); await m.answer_document(InputFile(fn)); os.remove(fn)

# 12. ADMIN FOYDALANUVCHILARNI BOSHQARISH
@dp.message_handler(text="🆕 Yangi so'rovlar")
async def adm_new(m: types.Message):
    pending = [u for u in db.get_all_users() if not u[4]]
    if not pending: return await m.answer("Yangi so'rovlar yo'q.")
    for u in pending:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅", callback_data="app_" + str(u[1])),
               InlineKeyboardButton("❌", callback_data="rej_" + str(u[1])))
        await m.answer("👤 " + str(u[2]) + "\n📱 " + str(u[3]), reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith(("app_", "rej_", "del_")))
async def adm_act(c: types.CallbackQuery):
    act, tid = c.data.split("_")
    tid = int(tid)
    
    if act == "app":
        db.approve_user(tid, True)
        try: await bot.send_message(tid, "✅ Tasdiqlandi!")
        except: pass
        await c.message.edit_text("✅ Tasdiqlandi")
    elif act == "rej":
        db.delete_user(tid)
        try: await bot.send_message(tid, "❌ Rad etildi")
        except: pass
        await c.message.edit_text("❌ Rad etildi")
    elif act == "del":
        db.delete_user(tid)
        await c.message.edit_text("🗑 O'chirildi")

@dp.message_handler(text="👥 Operatorlar reytingi")
async def adm_rank(m: types.Message):
    if m.from_user.id not in ADMIN_IDS: return
    lines = []
    for r in db.get_operator_ranking():
        lines.append("👤 " + str(r[0]) + ": <b>" + str(r[3]) + "</b>")
    txt = "<b>🏆 Reyting:</b>\n" + "\n".join(lines)
    await m.answer(txt)

# 13. CO-ADMIN
@dp.message_handler(commands=['coadmin'], state="*")
async def coadmin_ent(m: types.Message):
    await m.answer("Parol:", reply_markup=back_kb)
    await CoAdminSt.password.set()

@dp.message_handler(state=CoAdminSt.password)
async def coadmin_chk(m: types.Message, state: FSMContext):
    if m.text == COADMIN_PASSWORD:
        db.make_coadmin(m.from_user.id, True)
        await m.answer("✅ Siz Co-Adminsiz!", reply_markup=main_kb(m.from_user.id, True))
        await state.finish()
    else:
        await m.answer("Xato.")

# 14. QIDIRUV
@dp.message_handler(text="🔍 Raqam tekshirish")
async def search_start(m: types.Message):
    await m.answer("Oxirgi 4 raqam:", reply_markup=back_kb)
    await Search.query.set()

@dp.message_handler(state=Search.query)
async def search_process(m: types.Message, state: FSMContext):
    res = db.search_phone_by_digits(m.text)
    sid = m.from_user.id
    
    if not res:
        await m.answer("Topilmadi.", reply_markup=main_kb(sid, True))
    else:
        for r in res[:5]:
            ph, op, dt, st, cn, age, h, w, intr, op_id = r
            txt = "📱 " + str(ph) + "\n👤 " + str(op) + "\n📊 " + str(st) + "\n🕒 " + str(dt)
            await m.answer(txt)
        await m.answer("Tugadi.", reply_markup=main_kb(sid, True))
    await state.finish()

if __name__ == "__main__":
    print("Bot Python 3.6 muhitida ishga tushdi...")
    executor.start_polling(dp, skip_updates=True)
