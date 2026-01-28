import asyncio
import os
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import *
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

try:
    from db_manager import db
except ImportError:
    print("XATO: db_manager.py fayli topilmadi!")
    exit()

# --- SOZLAMALAR ---
TOKEN = "8143822107:AAFgSsJMeJ9SGdf1dQflBnExlvnsBIfRdzs"
ADMIN_IDS = [7044905076]
ADMIN_PASSWORD = "1122"
COADMIN_PASSWORD = "3344"

# --- STATES ---
class Reg(StatesGroup): name = State()
class AdminSt(StatesGroup): password = State(); add_nums = State(); set_limit = State()
class CoAdminSt(StatesGroup): password = State()
class Call(StatesGroup): 
    waiting_for_action = State() 
    phone = State(); status = State(); name = State()
    age = State(); height = State(); weight = State(); interest = State()
class ManualEntry(StatesGroup): phone = State(); action = State()
class Search(StatesGroup): query = State()

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# ================== KLAVIATURALAR ==================
back_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 Ortga")]], resize_keyboard=True)

def main_kb(uid, online=False):
    status_text = "Online ✅" if online else "Offline ❌"
    kb = [
        [KeyboardButton(text="📞 Nomer olish"), KeyboardButton(text="✍️ Raqam kiritish")],
        [KeyboardButton(text="🔍 Raqam tekshirish")],
        [KeyboardButton(text=f"🟢 Ish vaqti: {status_text}")],
        [KeyboardButton(text="📉 Bugungi qabul qilinmagan")],
        [KeyboardButton(text="📈 Shaxsiy statistikam")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

call_action_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="📞 Qo'ng'iroq qilingan (kotargan)")],
    [KeyboardButton(text="🔄 Qayta bog'lanildi")],
    [KeyboardButton(text="❌ Qo'ng'iroq qilinmadi")],
    [KeyboardButton(text="🚫 Aktiv emas / noto'g'ri")],
    [KeyboardButton(text="🔙 Ortga")]
], resize_keyboard=True)

admin_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="📊 Umumiy statistika"), KeyboardButton(text="👥 Operatorlar reytingi")],
    [KeyboardButton(text="➕ Raqam(lar) qo'shish"), KeyboardButton(text="⚙️ Limitni sozlash")],
    [KeyboardButton(text="📉 Kotarmaganlar (Excel)"), KeyboardButton(text="📞 Barcha raqamlar (Excel)")],
    [KeyboardButton(text="👤 Tasdiqlangan operatorlar"), KeyboardButton(text="🆕 Yangi so'rovlar")],
    [KeyboardButton(text="📅 Kunlik Excel"), KeyboardButton(text="📅 Haftalik Excel")], 
    [KeyboardButton(text="📅 Oylik Excel"), KeyboardButton(text="🧹 Tozalash")],
    [KeyboardButton(text="🔙 Asosiy Menyu")]
], resize_keyboard=True)

personal_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="📅 Kunlik hisobot (Excel)")],
    [KeyboardButton(text="📅 Haftalik hisobot (Excel)")],
    [KeyboardButton(text="🔙 Ortga")]
], resize_keyboard=True)

# ================== GLOBAL ORTGA ==================
@router.message(F.text == "🔙 Ortga")
async def global_cancel(m: Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    user = db.get_user(uid)
    if user and user[6]: db.set_current_number(uid, None)
    if user and user[4]: await m.answer("Asosiy menyu:", reply_markup=main_kb(uid, bool(user[5])))
    else: await m.answer("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())

# ================== START & REG ==================
@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    user = db.get_user(uid)
    if user and user[4]: await m.answer("Xush kelibsiz!", reply_markup=main_kb(uid, bool(user[5])))
    elif user and not user[4]: await m.answer("⏳ Hisobingiz admin tasdiqlashini kutmoqda.")
    else:
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]], resize_keyboard=True)
        await m.answer("Assalomu alaykum! Ro'yxatdan o'tish uchun raqamingizni yuboring:", reply_markup=kb)

@router.message(F.contact)
async def reg_contact(m: Message, state: FSMContext):
    phone = m.contact.phone_number
    if not phone.startswith("+"): phone = "+" + phone
    await state.update_data(phone=phone)
    await m.answer("Ism va familiyangizni kiriting:", reply_markup=back_kb)
    await state.set_state(Reg.name)

@router.message(Reg.name)
async def reg_name(m: Message, state: FSMContext):
    data = await state.get_data()
    if db.add_user(m.from_user.id, m.text, data['phone']):
        await m.answer("✅ So'rov yuborildi. Kuting.", reply_markup=ReplyKeyboardRemove())
    else: await m.answer("Siz allaqachon ro'yxatdasiz.")
    await state.clear()

# ================== OPERATOR: NOMER OLISH ==================
@router.message(F.text.startswith("🟢 Ish vaqti:"))
async def toggle_online(m: Message):
    uid = m.from_user.id
    user = db.get_user(uid)
    if not user or not user[4]: return await m.answer("Ruxsat yo'q.")
    new_status = not bool(user[5])
    db.set_online(uid, new_status)
    await m.answer(f"Holat o'zgardi.", reply_markup=main_kb(uid, new_status))

@router.message(F.text == "📞 Nomer olish")
async def get_number(m: Message, state: FSMContext):
    uid = m.from_user.id
    user = db.get_user(uid)
    if not user or not user[5]: return await m.answer("Avval Online bo'ling.")
    if user[6]: 
        await m.answer(f"Sizda faol raqam bor: <b>{user[6]}</b>\nNatijani tanlang:", reply_markup=call_action_kb)
        await state.set_state(Call.waiting_for_action)
        return
    
    limit = db.get_limit()
    count = db.get_today_count(uid)
    if count >= limit: return await m.answer(f"⛔️ Kunlik limit tugadi ({count}/{limit}).")
    
    data = db.get_free_number_full(uid) 
    if data:
        # phone, full_name, telegram_user, extra_info
        phone, name, tg, extra = data
        db.set_current_number(uid, phone)
        
        msg = (
            f"📞 <b>Yangi mijoz:</b>\n\n"
            f"👤 <b>Ism:</b> {name if name else 'Topilmadi'}\n"
            f"📱 <b>Tel:</b> <code>{phone}</code>\n"
            f"✈️ <b>Tg:</b> {tg if tg else 'Yo\'q'}\n"
            f"📝 <b>Info:</b> {extra if extra else 'Yo\'q'}\n\n"
            f"<i>Qo'ng'iroq qilib, natijani tanlang:</i>"
        )
        await m.answer(msg, reply_markup=call_action_kb)
        await state.set_state(Call.waiting_for_action)
    else: await m.answer("⚠️ Bazada bo'sh raqam qolmadi.")

@router.message(F.text == "✍️ Raqam kiritish")
async def manual_enter_start(m: Message, state: FSMContext):
    uid = m.from_user.id
    user = db.get_user(uid)
    if not user or not user[5]: return await m.answer("Avval Online bo'ling.")
    await m.answer("Mijoz raqamini kiriting:", reply_markup=back_kb)
    await state.set_state(ManualEntry.phone)

@router.message(ManualEntry.phone)
async def manual_enter_save(m: Message, state: FSMContext):
    phone = m.text.strip()
    if len(phone) < 7: return await m.answer("Noto'g'ri raqam.", reply_markup=back_kb)
    await state.update_data(phone=phone)
    await m.answer(f"Raqam: <b>{phone}</b>\nNatijani tanlang:", reply_markup=call_action_kb)
    await state.set_state(ManualEntry.action)

# ================== NATIJA QABUL QILISH ==================
@router.message(F.text.in_(["📞 Qo'ng'iroq qilingan (kotargan)", "🔄 Qayta bog'lanildi", "❌ Qo'ng'iroq qilinmadi", "🚫 Aktiv emas / noto'g'ri"]))
async def log_call_result(m: Message, state: FSMContext):
    uid = m.from_user.id
    user = db.get_user(uid)
    current_state = await state.get_state()
    
    phone = None
    if current_state == ManualEntry.action:
        d = await state.get_data(); phone = d.get('phone')
    else:
        if not user or not user[6]: return await m.answer("Faol raqam yo'q.")
        phone = user[6]

    st_map = {"📞 Qo'ng'iroq qilingan (kotargan)": "success", "🔄 Qayta bog'lanildi": "recalled", "❌ Qo'ng'iroq qilinmadi": "no_answer", "🚫 Aktiv emas / noto'g'ri": "invalid"}
    status = st_map[m.text]
    await state.update_data(phone=phone, status=status)

    if status in ["success", "recalled"]:
        await m.answer("Mijoz ismi:", reply_markup=back_kb)
        await state.set_state(Call.name)
    else:
        db.add_call({'op_id': uid, 'phone': phone, 'status': status})
        if user and user[6] == phone: db.set_current_number(uid, None)
        await state.clear()
        await m.answer("✅ Natija saqlandi!", reply_markup=main_kb(uid, True))

# Anketa
@router.message(Call.name)
async def c_name(m: Message, state: FSMContext): await state.update_data(name=m.text); await m.answer("Yosh:", reply_markup=back_kb); await state.set_state(Call.age)
@router.message(Call.age)
async def c_age(m: Message, state: FSMContext): await state.update_data(age=int(m.text) if m.text.isdigit() else 0); await m.answer("Bo'y:", reply_markup=back_kb); await state.set_state(Call.height)
@router.message(Call.height)
async def c_height(m: Message, state: FSMContext): await state.update_data(height=int(m.text) if m.text.isdigit() else 0); await m.answer("Vazn:", reply_markup=back_kb); await state.set_state(Call.weight)
@router.message(Call.weight)
async def c_weight(m: Message, state: FSMContext):
    await state.update_data(weight=int(m.text) if m.text.isdigit() else 0)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Ha (Qiziqdi)", callback_data="int_ha"), InlineKeyboardButton(text="❌ Yo'q", callback_data="int_yoq")]])
    await m.answer("Mijoz qiziqdimi?", reply_markup=kb)
    await state.set_state(Call.interest)

@router.callback_query(Call.interest)
async def c_interest(c: CallbackQuery, state: FSMContext):
    ans = "Ha" if c.data == "int_ha" else "Yo'q"
    d = await state.get_data()
    uid = c.from_user.id
    db.add_call({'op_id': uid, 'phone': d['phone'], 'status': d['status'], 'name': d.get('name'), 'age': d.get('age'), 'height': d.get('height'), 'weight': d.get('weight'), 'interest': ans})
    user = db.get_user(uid)
    if user and user[6] == d['phone']: db.set_current_number(uid, None)
    await state.clear()
    await c.message.edit_text(f"Qiziqish: {ans}"); await c.message.answer("✅ Saqlandi!", reply_markup=main_kb(uid, True))

# ================== ADMIN ==================
@router.message(Command("admin"))
async def admin_ent(m: Message, state: FSMContext):
    if m.from_user.id in ADMIN_IDS: await m.answer("Parol:", reply_markup=back_kb); await state.set_state(AdminSt.password)
@router.message(AdminSt.password)
async def admin_chk(m: Message, state: FSMContext):
    if m.text == ADMIN_PASSWORD: await m.answer("Admin Panel", reply_markup=admin_kb); await state.clear()
    else: await m.answer("Xato.")

@router.message(F.text == "➕ Raqam(lar) qo'shish")
async def adm_add(m: Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS: return
    await m.answer("Excel fayl (.xlsx) yuboring:", reply_markup=back_kb)
    await state.set_state(AdminSt.add_nums)

# --- EXCEL PARSER ---
@router.message(AdminSt.add_nums, F.document)
async def adm_upload_excel(m: Message, state: FSMContext, bot: Bot):
    if not m.document.file_name.endswith('.xlsx'):
        return await m.answer("Faqat .xlsx fayl yuboring!")
    
    file_id = m.document.file_id
    file = await bot.get_file(file_id)
    destination = f"import_{m.from_user.id}.xlsx"
    await bot.download_file(file.file_path, destination)
    
    added, updated = 0, 0 
    
    try:
        wb = load_workbook(destination, data_only=True)
        ws = wb.active
        
        # 1. HEADER QIDIRISH
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

        # 2. O'QISH
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
            
        await m.answer(f"✅ Fayl yuklandi!\n🆕 Qo'shildi: {added}\n♻️ Yangilandi: {updated}", reply_markup=admin_kb)
        
    except Exception as e:
        await m.answer(f"Xatolik: {e}")
    finally:
        if os.path.exists(destination): os.remove(destination)
    await state.clear()

# --- ADMIN STATISTIKA ---
@router.message(F.text == "📊 Umumiy statistika")
async def adm_stats(m: Message):
    if m.from_user.id not in ADMIN_IDS: return
    t, s, n, i = db.get_general_stats()
    await m.answer(f"<b>📊 Statistika</b>\n📞 Jami: {t}\n✅ Kotargan: {s}\n❌ Yo'q: {n}\n🚫 Yaroqsiz: {i}")

@router.message(F.text == "👥 Operatorlar reytingi")
async def adm_rank(m: Message):
    if m.from_user.id not in ADMIN_IDS: return
    txt = "<b>🏆 Reyting:</b>\n" + "\n".join([f"👤 {r[0]}: <b>{r[3]}</b>" for r in db.get_operator_ranking()])
    await m.answer(txt)

# --- ADMIN BOSHQA ---
@router.message(F.text == "⚙️ Limitni sozlash")
async def set_limit_start(m: Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS: return
    await m.answer(f"Limit: {db.get_limit()}", reply_markup=back_kb); await state.set_state(AdminSt.set_limit)
@router.message(AdminSt.set_limit)
async def set_limit_save(m: Message, state: FSMContext):
    if m.text.isdigit(): db.set_limit(int(m.text)); await m.answer("OK", reply_markup=admin_kb); await state.clear()

@router.message(F.text.in_(["📉 Kotarmaganlar (Excel)", "📞 Barcha raqamlar (Excel)"]))
async def adm_excels(m: Message):
    if m.from_user.id not in ADMIN_IDS: return
    if "Kotarmaganlar" in m.text:
        data = db.get_no_answer_numbers(); fn = "NoAns.xlsx"; header = ["Tel"]
    else:
        data = db.get_all_numbers(); fn = "AllNums.xlsx"; header = ["Tel", "Ishlatilgan", "Operator", "Vaqt"]
    
    wb = Workbook(); ws = wb.active; ws.append(header)
    for r in data: ws.append(list(r))
    wb.save(fn); await m.answer_document(FSInputFile(fn)); os.remove(fn)

@router.message(F.text == "🆕 Yangi so'rovlar")
async def adm_new(m: Message):
    pending = [u for u in db.get_all_users() if not u[4]]
    if not pending: return await m.answer("Yo'q.")
    for u in pending:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅", callback_data=f"app_{u[1]}"), InlineKeyboardButton(text="❌", callback_data=f"rej_{u[1]}") ]])
        await m.answer(f"👤 {u[2]}\n📱 {u[3]}", reply_markup=kb)

@router.callback_query(F.data.startswith(("app_", "rej_", "del_")))
async def adm_act(c: CallbackQuery):
    act, tid = c.data.split("_"); tid = int(tid)
    if act == "app": db.approve_user(tid, True); await bot.send_message(tid, "✅ Tasdiqlandi!"); await c.message.edit_text("✅ OK")
    elif act == "rej": db.delete_user(tid); await bot.send_message(tid, "❌ Rad etildi."); await c.message.edit_text("❌ DEL")
    elif act == "del": db.delete_user(tid); await c.message.edit_text("🗑 Deleted")

@router.message(F.text == "👤 Tasdiqlangan operatorlar")
async def adm_appr(m: Message):
    if m.from_user.id not in ADMIN_IDS: return
    for u in [u for u in db.get_all_users() if u[4]]:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_{u[1]}") ]])
        await m.answer(f"{'🟢' if u[5] else '🔴'} {u[2]} | {u[3]}", reply_markup=kb)

@router.message(F.text == "🧹 Tozalash")
async def adm_clear_ask(m: Message):
    if m.from_user.id in ADMIN_IDS: await m.answer("Tozalansinmi?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Ha", callback_data="clear_yes"), InlineKeyboardButton(text="❌ Yo'q", callback_data="clear_no")]]))
@router.callback_query(F.data.startswith("clear_"))
async def adm_clear_confirm(c: CallbackQuery):
    if "yes" in c.data: db.clear_numbers_and_calls(); await c.message.edit_text("Tozalandi.")
    else: await c.message.edit_text("Bekor qilindi.")

# --- CO-ADMIN & SEARCH ---
@router.message(Command("coadmin"))
async def coadmin_ent(m: Message, state: FSMContext): await m.answer("Parol:", reply_markup=back_kb); await state.set_state(CoAdminSt.password)
@router.message(CoAdminSt.password)
async def coadmin_chk(m: Message, state: FSMContext):
    if m.text == COADMIN_PASSWORD: db.make_coadmin(m.from_user.id, True); await m.answer("✅ Siz Co-Adminsiz!", reply_markup=main_kb(m.from_user.id, True)); await state.clear()
    else: await m.answer("Xato.")

@router.message(F.text == "🔍 Raqam tekshirish")
async def search_start(m: Message, state: FSMContext): await m.answer("Oxirgi 4 raqam:", reply_markup=back_kb); await state.set_state(Search.query)

# --- YANGILANGAN QIDIRUV (BUTTON BILAN) ---
@router.message(Search.query)
async def search_process(m: Message, state: FSMContext):
    res = db.search_phone_by_digits(m.text)
    sid = m.from_user.id; s_user = db.get_user(sid)
    # Admin yoki Co-admin ekanligini tekshirish
    is_priv = (sid in ADMIN_IDS) or (s_user and len(s_user)>7 and s_user[7])
    
    if not res: await m.answer("Topilmadi.", reply_markup=main_kb(sid, True))
    else:
        for r in res[:5]:
            ph, op, dt, st, cn, age, h, w, intr, op_id = r
            txt = f"📱 {ph}\n👤 {op}\n📊 {st}\n🕒 {dt}\n\n"
            
            # Agar Admin bo'lsa va Operator boshqa odam bo'lsa -> Tugma chiqaramiz
            if is_priv and op_id and op_id != sid:
                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✅ Eslatma yuborish", callback_data=f"ntf_y_{op_id}_{ph}"),
                    InlineKeyboardButton(text="❌ Yopish", callback_data="ntf_n")
                ]])
                await m.answer(txt, reply_markup=kb)
            else:
                await m.answer(txt)
                
        await m.answer("Qidiruv tugadi.", reply_markup=main_kb(sid, True))
    await state.clear()

# --- YANGI CALLBACK (Eslatma yuborish uchun) ---
@router.callback_query(F.data.startswith("ntf_"))
async def process_notification_callback(c: CallbackQuery):
    if c.data == "ntf_n":
        await c.message.delete()
    elif c.data.startswith("ntf_y_"):
        try:
            _, _, op_id, phone = c.data.split("_")
            # Operatorga xabar yuborish
            await bot.send_message(
                chat_id=int(op_id), 
                text=f"🔔 <b>DIQQAT, ESLATMA!</b>\n\nSiz ishlagan raqam: <b>{phone}</b>\nAdmin tomonidan qayta tekshirildi.\nIltimos, ushbu mijoz bilan qayta bog'laning!"
            )
            await c.message.edit_text(f"{c.message.text}\n\n✅ <b>Eslatma yuborildi!</b>")
        except Exception as e:
            await c.message.answer(f"Xatolik: {e}")

# --- EXCEL REPORT & STATS ---
async def generate_excel(m, period, op_id):
    now = datetime.now()
    if period == "kunlik": s, e = now.replace(hour=0, minute=0, second=0), now + timedelta(days=1)
    elif period == "haftalik": s = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0); e = s + timedelta(days=7)
    elif period == "oylik": s = now.replace(day=1, hour=0, minute=0, second=0); e = (s.replace(month=s.month+1) if s.month < 12 else s.replace(year=s.year+1, month=1))
    
    rows = db.get_calls_stats(s, e, op_id)
    if not rows: return await m.answer("Ma'lumot yo'q.")
    wb = Workbook(); ws = wb.active; ws.append(["Op ID", "Op", "Tel", "Status", "Mijoz", "Yosh", "Bo'y", "Vazn", "Qiziqish", "Vaqt"])
    for r in rows: ws.append(list(r))
    fn = f"Rep_{period}.xlsx"; wb.save(fn); await m.answer_document(FSInputFile(fn)); os.remove(fn)

@router.message(F.text.in_(["📅 Kunlik Excel", "📅 Haftalik Excel", "📅 Oylik Excel"]))
async def adm_exc(m: Message): 
    if m.from_user.id in ADMIN_IDS: 
        p = "kunlik" if "Kunlik" in m.text else "haftalik" if "Haftalik" in m.text else "oylik"
        await generate_excel(m, p, None)

@router.message(F.text == "📉 Bugungi qabul qilinmagan")
async def today_no(m: Message):
    nums = db.get_today_no_answers(m.from_user.id)
    txt = "📉 Bugungi ko'tarmaganlar:\n" + "\n".join([f"❌ {r[0]}" for r in nums]) if nums else "Yo'q."
    await m.answer(txt)

@router.message(F.text == "📈 Shaxsiy statistikam")
async def my_st(m: Message): await m.answer("Tanlang:", reply_markup=personal_kb)
@router.message(F.text.contains("hisobot (Excel)"))
async def my_ex(m: Message): await generate_excel(m, "kunlik" if "Kunlik" in m.text else "haftalik", m.from_user.id)

# --- ENTRY POINT ---
@router.message(F.text == "🔙 Asosiy Menyu")
async def back_main(m: Message, state: FSMContext): await cmd_start(m, state)

async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    