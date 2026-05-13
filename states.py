from aiogram.fsm.state import State, StatesGroup

class LangFlow(StatesGroup):
    choosing = State()

class ConvertFlow(StatesGroup):
    awaiting_file = State()
    awaiting_text = State()
    awaiting_text_confirmation = State()

class ImgConvertFlow(StatesGroup):
    awaiting_image = State()

class CompressFlow(StatesGroup):
    awaiting_file = State()

class TranslitFlow(StatesGroup):
    awaiting_text = State()

class PaymentFlow(StatesGroup):
    choosing_kind = State()
    choosing_plan = State()
    awaiting_proof = State()

class ContactAdminFlow(StatesGroup):
    awaiting_message = State()

class OcrFlow(StatesGroup):
    awaiting_image = State()
    choosing_lang = State()

class AdminFlow(StatesGroup):
    main = State()
    viewing_payments = State()
    awaiting_broadcast = State()
    awaiting_premium_user_id = State()
    awaiting_premium_days = State()
