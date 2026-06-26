import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, FSInputFile, InputMediaPhoto
from aiogram.filters import Command

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.getenv('BOT_TOKEN')
PRICE_LIST = {
    "Эндофем Про Супп №10": {"price": 125000, "nds": 15000},
    "Ловикс 150 мл": {"price": 107143, "nds": 12857.16},
    "Октенидин+Мирамистин 100 мл": {"price": 53575, "nds": 6429},
    "Октенидин+Мирамистин 50 мл": {"price": 50000, "nds": 6000},
}

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class OrderState(StatesGroup):
    choosing_product = State()
    entering_quantity = State()
    after_product = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_product_kb():
    buttons = [[KeyboardButton(text=name)] for name in PRICE_LIST.keys()]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def get_action_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Продолжить покупки"), KeyboardButton(text="Оформить заказ")]
    ], resize_keyboard=True)

def format_money(amount):
    return f"{amount:,.0f}".replace(",", " ")

# --- ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.set_data({'cart': []})

    # Отправляем приветственный текст СРАЗУ, не дожидаясь загрузки фото
    welcome_text = (
        "<b>═══════════════════════════════════</b>\n"
        "       <b>Добро пожаловать</b>\n"
        "          в <b>SAA MED</b>\n"
        "<b>═══════════════════════════════════</b>\n\n"
        "Мы рады видеть вас в нашем магазине качественной медицинской продукции.\n\n"
        "<b>Как сделать заказ:</b>\n"
        "  1. Выберите товар из списка ниже\n"
        "  2. Укажите необходимое количество\n"
        "  3. Добавьте в корзину или оформите заказ\n\n"
        "<b>───────────────────────────────────</b>\n"
        "<b>Наш ассортимент:</b>\n"
    )

    for name, info in PRICE_LIST.items():
        total = info['price'] + info['nds']
        welcome_text += f"\n  • <b>{name}</b>\n     {format_money(total)} сум\n"

    welcome_text += "\n<b>───────────────────────────────────</b>\n<i>Выберите товар из списка ниже:</i>"

    # Параллельно отправляем фото и текст — бот отвечает мгновенно
    base_dir = os.path.dirname(os.path.abspath(__file__))
    img_folder = os.path.join(base_dir, "img")
    photo_files = ["1.png", "2.png", "3.png"]

    async def send_photos():
        media_group = []
        for p in photo_files:
            path = os.path.join(img_folder, p)
            if os.path.exists(path):
                media_group.append(InputMediaPhoto(media=FSInputFile(path)))
        if media_group:
            try:
                await message.answer_media_group(media=media_group)
            except Exception:
                pass  # Если фото не загрузятся — не блокируем работу бота

    # Запускаем отправку фото в фоне и сразу отвечаем текстом
    asyncio.create_task(send_photos())
    await message.answer(welcome_text, reply_markup=get_product_kb(), parse_mode="HTML")
    await state.set_state(OrderState.choosing_product)

@dp.message(OrderState.choosing_product)
async def choose_product(message: types.Message, state: FSMContext):
    product_name = message.text

    if product_name not in PRICE_LIST:
        return await message.answer(
            "<b>⚠ Ошибка</b>\n\nПожалуйста, выберите товар из списка ниже, нажав на кнопку.",
            reply_markup=get_product_kb(),
            parse_mode="HTML"
        )

    await state.update_data(current_product=product_name)

    info = PRICE_LIST[product_name]
    price_with_nds = info['price'] + info['nds']

    product_info = (
        "<b>┌───────────────────────────────────┐</b>\n"
        "<b>│  Выбранный товар                  │</b>\n"
        "<b>└───────────────────────────────────┘</b>\n\n"
        f"<b>{product_name}</b>\n\n"
        f"   Цена:  <b>{format_money(price_with_nds)} сум</b>\n"
        "   <i>(включая НДС)</i>\n\n"
        "<b>───────────────────────────────────</b>\n"
        "<i>Введите количество (в штуках):</i>"
    )

    await message.answer(product_info, parse_mode="HTML")
    await state.set_state(OrderState.entering_quantity)

@dp.message(OrderState.entering_quantity)
async def enter_qty(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        return await message.answer(
            "<b>Неверный формат</b>\n\nПожалуйста, введите целое положительное число.\n\n<i>Пример:</i> <code>5</code>",
            parse_mode="HTML"
        )

    quantity = int(message.text)
    data = await state.get_data()
    cart = data.get('cart', [])
    cart.append({'name': data['current_product'], 'qty': quantity})
    await state.update_data(cart=cart)

    info = PRICE_LIST[data['current_product']]
    item_total = (info['price'] + info['nds']) * quantity

    success_msg = (
        "<b>┌───────────────────────────────────┐</b>\n"
        "<b>│    Товар добавлен в корзину       │</b>\n"
        "<b>└───────────────────────────────────┘</b>\n\n"
        "<b>Содержимое корзины:</b>\n"
    )

    cart_total = 0
    for item in cart:
        item_info = PRICE_LIST[item['name']]
        item_cost = (item_info['price'] + item_info['nds']) * item['qty']
        cart_total += item_cost
        success_msg += f"\n  • {item['name']}\n     {item['qty']} шт. — {format_money(item_cost)} сум"

    success_msg += (
        f"\n\n<b>───────────────────────────────────</b>\n"
        f"<b>Общая сумма:</b>  <b>{format_money(cart_total)} сум</b>\n"
        f"<b>───────────────────────────────────</b>\n\n"
        f"<i>Выберите действие:</i>"
    )

    await message.answer(success_msg, reply_markup=get_action_kb(), parse_mode="HTML")
    await state.set_state(OrderState.after_product)

@dp.message(OrderState.after_product, F.text == "Продолжить покупки")
async def continue_buying(message: types.Message, state: FSMContext):
    await message.answer(
        "<b>───────────────────────────────────</b>\n\n<i>Выберите следующий товар из списка:</i>",
        reply_markup=get_product_kb(),
        parse_mode="HTML"
    )
    await state.set_state(OrderState.choosing_product)

@dp.message(OrderState.after_product, F.text == "Оформить заказ")
async def finish_order(message: types.Message, state: FSMContext):
    data = await state.get_data()

    summary = (
        "<b>═══════════════════════════════════</b>\n"
        "          <b>ВАШ ЗАКАЗ</b>\n"
        "<b>═══════════════════════════════════</b>\n\n"
    )

    total_sum, total_nds = 0, 0
    item_number = 1

    for item in data['cart']:
        info = PRICE_LIST[item['name']]
        cost = info['price'] * item['qty']
        nds = info['nds'] * item['qty']
        item_total = cost + nds

        summary += f"<b>{item_number}. {item['name']}</b>\n"
        summary += f"     Количество:  {item['qty']} шт.\n"
        summary += f"     Стоимость:   {format_money(item_total)} сум\n"
        summary += f"     НДС:         {format_money(nds)} сум\n"
        summary += "     ─────────────────────────\n"

        total_sum += cost
        total_nds += nds
        item_number += 1

    grand_total = total_sum + total_nds

    summary += (
        f"\n<b>═══════════════════════════════════</b>\n"
        f"          <b>ИТОГО К ОПЛАТЕ</b>\n"
        f"<b>═══════════════════════════════════</b>\n"
        f"  Сумма без НДС:  {format_money(total_sum)} сум\n"
        f"  НДС:            {format_money(total_nds)} сум\n"
        f"<b>═══════════════════════════════════</b>\n"
        f"  <b>ОБЩАЯ СУММА:</b>\n"
        f"  <b>{format_money(grand_total)} сум</b>\n"
        f"<b>═══════════════════════════════════</b>\n\n"
        f"<b>═══════════════════════════════════</b>\n"
        f"        <b>РЕКВИЗИТЫ СААМЕД</b>\n"
        f"<b>═══════════════════════════════════</b>\n"
        f"  Адрес:  Toshkent Shahri,\n"
        f"          Uchtepa tumani\n\n"
        f"  Банк:   Biznesni rivojlantirish\n"
        f"          banki\n\n"
        f"  Р/С:    2020 8000 1074 2309 5001\n"
        f"<b>═══════════════════════════════════</b>\n\n"
        f"<i>Спасибо за заказ!</i>\n"
        f"<i>Мы свяжемся с вами в ближайшее время.</i>"
    )

    await message.answer(summary, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())