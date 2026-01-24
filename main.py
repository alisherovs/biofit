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
from openpyxl import Workbook
from openpyxl.styles import Font

try:
    from db_manager import db
except ImportError:
    print("XATO: db_manager.py fayli topilmadi!")
    exit()

TOKEN = "8143822107:AAFgSsJMeJ9SGdf1dQflBnExlvnsBIfRdzs"
ADMIN_IDS = [7044905076]
ADMIN_PASSWORD = "1122"

class Reg(StatesGroup): name = State()
class AdminSt(StatesGroup): password = State(); add_nums = State(); set_limit = State()
class Call(StatesGroup): phone = State(); name = State(); age = State(); height = State(); weight = State()
class Search(StatesGroup): query = State()

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# ================== KLAVIATURALAR ==================
def main_kb(uid, online=False):
    status_text = "Online ✅" if online else "Offline ❌"
    kb = [
        [KeyboardButton(text="📞 Nomer olish"), KeyboardButton(text="🔍 Raqam tekshirish")],
        [KeyboardButton(text=f"🟢 Ish vaqti: {status_text}")],
        [KeyboardButton(text="📞 Qo'ng'iroq qilingan (kotargan)")],
        [KeyboardButton(text="❌ Qo'ng'iroq qilinmadi")],
        [KeyboardButton(text="🚫 Aktiv emas / noto'g'ri")],
        [KeyboardButton(text="🔙 Ortga")],
        [KeyboardButton(text="📈 Shaxsiy statistikam")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

admin_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="📊 Umumiy statistika"), KeyboardButton(text="👥 Operatorlar reytingi")],
    [KeyboardButton(text="➕ Raqam(lar) qo'shish"), KeyboardButton(text="⚙️ Limitni sozlash")],
    [KeyboardButton(text="📉 Kotarmaganlar (Excel)"), KeyboardButton(text="📞 Barcha raqamlar (Excel)")],
    [KeyboardButton(text="👤 Tasdiqlangan operatorlar"), KeyboardButton(text="🆕 Yangi so'rovlar")],
    # --- HAFTALIK EXCEL QAYTARILDI ---
    [KeyboardButton(text="📅 Kunlik Excel"), KeyboardButton(text="📅 Haftalik Excel")], 
    [KeyboardButton(text="📅 Oylik Excel"), KeyboardButton(text="🧹 Tozalash")],
    [KeyboardButton(text="🔙 Asosiy Menyu")]
], resize_keyboard=True)

personal_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="📅 Kunlik hisobot (Excel)")],
    [KeyboardButton(text="📅 Haftalik hisobot (Excel)")],
    [KeyboardButton(text="🔙 Ortga")]
], resize_keyboard=True)

# ================== START & REG ==================
@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    uid = m.from_user.id
    user = db.get_user(uid)
    if user and user[4]:
        await m.answer("Xush kelibsiz!", reply_markup=main_kb(uid, bool(user[5])))
    elif user and not user[4]:
        await m.answer("⏳ Hisobingiz admin tomonidan tasdiqlanishini kuting.")
    else:
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]], resize_keyboard=True)
        await m.answer("Assalomu alaykum! Ro'yxatdan o'tish uchun raqamingizni yuboring:", reply_markup=kb)

@router.message(F.contact)
async def reg_contact(m: Message, state: FSMContext):
    phone = m.contact.phone_number
    if not phone.startswith("+"): phone = "+" + phone
    await state.update_data(phone=phone)
    await m.answer("Ism va familiyangizni kiriting:")
    await state.set_state(Reg.name)

@router.message(Reg.name)
async def reg_name(m: Message, state: FSMContext):
    data = await state.get_data()
    uid = m.from_user.id
    if db.add_user(uid, m.text, data['phone']):
        await m.answer("✅ So'rov yuborildi. Kuting.", reply_markup=ReplyKeyboardRemove())
    else:
        await m.answer("Siz allaqachon ro'yxatdasiz.")
    await state.clear()

# ================== OPERATOR ==================
@router.message(F.text.startswith("🟢 Ish vaqti:"))
async def toggle_online(m: Message):
    uid = m.from_user.id
    user = db.get_user(uid)
    if not user or not user[4]: return await m.answer("Ruxsat yo'q.")
    new_status = not bool(user[5])
    db.set_online(uid, new_status)
    await m.answer(f"Holat o'zgardi.", reply_markup=main_kb(uid, new_status))

@router.message(F.text == "📞 Nomer olish")
async def get_number(m: Message):
    uid = m.from_user.id
    user = db.get_user(uid)
    if not user or not user[5]: return await m.answer("Avval Online bo'ling.")
    if user[6]: return await m.answer(f"Sizda faol raqam bor: <b>{user[6]}</b>")
    
    limit = db.get_limit()
    count = db.get_today_count(uid)
    if count >= limit:
        return await m.answer(f"⛔️ <b>Kunlik limit tugadi!</b>\nSiz bugun {count} ta raqam bilan ishladingiz.\nLimit: {limit} ta.")
    
    num = db.get_free_number(uid)
    if num:
        db.set_current_number(uid, num)
        await m.answer(f"📞 Yangi raqam: <b>{num}</b>\n(Bugungi hisob: {count+1}/{limit})", reply_markup=main_kb(uid, True))
    else: await m.answer("⚠️ Bazada bo'sh raqam qolmadi.")

@router.message(F.text.in_(["📞 Qo'ng'iroq qilingan (kotargan)", "❌ Qo'ng'iroq qilinmadi", "🚫 Aktiv emas / noto'g'ri"]))
async def log_call(m: Message, state: FSMContext):
    uid = m.from_user.id
    user = db.get_user(uid)
    if not user or not user[5]: return await m.answer("Online bo'ling.")
    if not user[6]: return await m.answer("Faol raqam yo'q.")
    
    status_map = {"📞 Qo'ng'iroq qilingan (kotargan)": "success", "❌ Qo'ng'iroq qilinmadi": "no_answer", "🚫 Aktiv emas / noto'g'ri": "invalid"}
    await state.update_data(status=status_map[m.text], phone=user[6])
    if status_map[m.text] == "success":
        await m.answer("Mijoz ismi:"); await state.set_state(Call.name)
    else: await save_db_call(m, state, uid)

@router.message(Call.name)
async def c_name(m: Message, state: FSMContext): await state.update_data(name=m.text); await m.answer("Yosh:"); await state.set_state(Call.age)
@router.message(Call.age)
async def c_age(m: Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("Raqam yozing.")
    await state.update_data(age=int(m.text)); await m.answer("Bo'y:"); await state.set_state(Call.height)
@router.message(Call.height)
async def c_height(m: Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("Raqam yozing.")
    await state.update_data(height=int(m.text)); await m.answer("Vazn:"); await state.set_state(Call.weight)
@router.message(Call.weight)
async def c_weight(m: Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("Raqam yozing.")
    await state.update_data(weight=int(m.text)); await save_db_call(m, state, m.from_user.id)

async def save_db_call(m: Message, state: FSMContext, uid: int):
    data = await state.get_data()
    db.add_call({'op_id': uid, 'phone': data['phone'], 'status': data['status'],
                 'name': data.get('name'), 'age': data.get('age'), 'height': data.get('height'), 'weight': data.get('weight')})
    db.set_current_number(uid, None)
    await state.clear()
    await m.answer("✅ Saqlandi!", reply_markup=main_kb(uid, True))

# ================== QIDIRUV ==================
@router.message(F.text == "🔍 Raqam tekshirish")
async def search_start(m: Message, state: FSMContext):
    await m.answer("🔎 Tekshirmoqchi bo'lgan raqamingizning <b>oxirgi 4 ta raqamini</b> kiriting:"); await state.set_state(Search.query)
@router.message(Search.query)
async def search_process(m: Message, state: FSMContext):
    query = m.text.strip()
    if not query.isdigit(): return await m.answer("❌ Raqam kiriting.")
    results = db.search_phone_by_digits(query)
    if not results: await m.answer("❌ Bog'lanilmagan.")
    else:
        text = f"🔎 <b>Topildi ({len(results)} ta):</b>\n\n"
        for res in results[:5]: 
            phone, op_name, date, status, c_name, age, height, weight = res
            status_txt = {"success": "✅ Kotargan", "no_answer": "❌ Kotarmagan", "invalid": "🚫 Aktiv"}.get(status, status)
            info = f"   👤 {c_name}, {age} yosh\n" if status == "success" else ""
            text += (f"📱 <b>{phone}</b>\n👨‍💻 Op: {op_name}\n🕒 {date[:16]}\n📊 {status_txt}\n{info}➖➖➖➖\n")
        await m.answer(text)
    await state.clear()

# ================== ADMIN PANEL ==================
@router.message(Command("admin"))
async def admin_ent(m: Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS: return
    await m.answer("Parol:"); await state.set_state(AdminSt.password)
@router.message(AdminSt.password)
async def admin_chk(m: Message, state: FSMContext):
    if m.text == ADMIN_PASSWORD: await m.answer("Admin Panel", reply_markup=admin_kb); await state.clear()
    else: await m.answer("Xato.")

@router.message(F.text == "🔙 Asosiy Menyu")
async def admin_back(m: Message, state: FSMContext): await cmd_start(m, state)

@router.message(F.text == "⚙️ Limitni sozlash")
async def set_limit_start(m: Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS: return
    current = db.get_limit()
    await m.answer(f"Hozirgi kunlik limit: <b>{current} ta</b>.\nYangi limitni kiriting:"); await state.set_state(AdminSt.set_limit)
@router.message(AdminSt.set_limit)
async def set_limit_save(m: Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("Faqat raqam yozing.")
    db.set_limit(int(m.text))
    await m.answer(f"✅ Yangi limit o'rnatildi: <b>{m.text} ta</b>"); await state.clear()

@router.message(F.text == "➕ Raqam(lar) qo'shish")
async def adm_add(m: Message, state: FSMContext):
    if m.from_user.id not in ADMIN_IDS: return
    await m.answer("Raqamlarni yuboring:"); await state.set_state(AdminSt.add_nums)
@router.message(AdminSt.add_nums)
async def adm_save(m: Message, state: FSMContext):
    c, u = db.add_numbers([x for x in re.split(r'[,\s\n]+', m.text.strip()) if x])
    await m.answer(f"✅ Qo'shildi: {c} ta\n♻️ Qayta tiklandi: {u} ta"); await state.clear()

@router.message(F.text == "📉 Kotarmaganlar (Excel)")
async def adm_no_answer_excel(m: Message):
    if m.from_user.id not in ADMIN_IDS: return
    nums = db.get_no_answer_numbers()
    if not nums: return await m.answer("Kotarmagan raqamlar yo'q.")
    wb = Workbook(); ws = wb.active; ws.append(["Telefon Raqam"])
    for r in nums: ws.append([r[0]])
    fn = "Kotarmaganlar.xlsx"; wb.save(fn); await m.answer_document(FSInputFile(fn)); os.remove(fn)

@router.message(F.text == "🆕 Yangi so'rovlar")
async def adm_new(m: Message):
    if m.from_user.id not in ADMIN_IDS: return
    pending = [u for u in db.get_all_users() if not u[4]]
    if not pending: return await m.answer("So'rov yo'q.")
    for u in pending:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅", callback_data=f"app_{u[1]}"), InlineKeyboardButton(text="❌", callback_data=f"rej_{u[1]}") ]])
        await m.answer(f"👤 {u[2]}\n📱 {u[3]}", reply_markup=kb)
@router.callback_query(F.data.startswith(("app_", "rej_", "del_")))
async def adm_act(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS: return
    act, tid = c.data.split("_"); tid = int(tid)
    if act == "app": db.approve_user(tid, True); await bot.send_message(tid, "✅ Tasdiqlandi!"); await c.message.edit_text("✅ OK")
    elif act == "rej": db.delete_user(tid); await bot.send_message(tid, "❌ Rad etildi."); await c.message.edit_text("❌ DEL")
    elif act == "del": db.delete_user(tid); await c.message.edit_text("🗑 Deleted")

@router.message(F.text == "👤 Tasdiqlangan operatorlar")
async def adm_appr(m: Message):
    if m.from_user.id not in ADMIN_IDS: return
    approved = [u for u in db.get_all_users() if u[4]]
    if not approved: return await m.answer("Yo'q.")
    for u in approved:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_{u[1]}") ]])
        await m.answer(f"{'🟢' if u[5] else '🔴'} {u[2]}\n📱 {u[3]}", reply_markup=kb)

# --- ADMIN EXCEL HANDLERS (HAFTALIK QO'SHILDI) ---
@router.message(F.text.in_(["📅 Kunlik Excel", "📅 Haftalik Excel", "📅 Oylik Excel"]))
async def adm_excel(m: Message):
    if m.from_user.id not in ADMIN_IDS: return
    if "Kunlik" in m.text: p = "kunlik"
    elif "Haftalik" in m.text: p = "haftalik"
    else: p = "oylik"
    await generate_excel(m, p, None)

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

@router.message(F.text == "📞 Barcha raqamlar (Excel)")
async def admin_all_nums(m: Message):
    if m.from_user.id not in ADMIN_IDS: return
    wb = Workbook(); ws = wb.active; ws.append(["Raqam", "Ishlatilgan", "Operator", "Vaqt"])
    for r in db.get_all_numbers(): ws.append([r[0], "Ha" if r[1] else "Yo'q", r[2] or "", str(r[3]) or ""])
    wb.save("nums.xlsx"); await m.answer_document(FSInputFile("nums.xlsx")); os.remove("nums.xlsx")

@router.message(F.text == "🧹 Tozalash")
async def adm_clear_ask(m: Message):
    if m.from_user.id not in ADMIN_IDS: return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Ha", callback_data="clear_yes"), InlineKeyboardButton(text="❌ Yo'q", callback_data="clear_no")]])
    await m.answer("⚠️ Barcha ma'lumotlar o'chadi! Tasdiqlaysizmi?", reply_markup=kb)
@router.callback_query(F.data.startswith("clear_"))
async def adm_clear_confirm(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS: return
    if "yes" in c.data: db.clear_numbers_and_calls(); await c.message.edit_text("✅ Tozalandi.")
    else: await c.message.edit_text("❌ Bekor qilindi.")

# --- UTILS ---
async def generate_excel(m, period, op_id):
    now = datetime.now()
    if period == "kunlik": s, e = now.replace(hour=0, minute=0, second=0), now + timedelta(days=1)
    elif period == "haftalik": s = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0); e = s + timedelta(days=7)
    elif period == "oylik": s = now.replace(day=1, hour=0, minute=0, second=0); e = (s.replace(month=s.month+1) if s.month < 12 else s.replace(year=s.year+1, month=1))
    
    rows = db.get_calls_stats(s, e, op_id)
    if not rows: return await m.answer("Ma'lumot topilmadi.")
    wb = Workbook(); ws = wb.active; ws.append(["Op ID", "Op Ismi", "Mijoz Tel", "Status", "Mijoz Ism", "Yosh", "Bo'y", "Vazn", "Vaqt"])
    for r in rows: ws.append(list(r))
    fn = f"Rep_{period}.xlsx"; wb.save(fn); await m.answer_document(FSInputFile(fn)); os.remove(fn)

@router.message(F.text == "📈 Shaxsiy statistikam")
async def my_stats(m: Message): await m.answer("Hisobot turi:", reply_markup=personal_kb)
@router.message(F.text.contains("hisobot (Excel)"))
async def gen_my_excel(m: Message):
    uid = m.from_user.id
    p = "kunlik" if "Kunlik" in m.text else "haftalik"
    await generate_excel(m, p, uid)
@router.message(F.text == "🔙 Ortga")
async def back(m: Message, state: FSMContext): await cmd_start(m, state)

async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    