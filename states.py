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
