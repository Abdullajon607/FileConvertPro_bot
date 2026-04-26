from aiogram.fsm.state import State, StatesGroup

class LangFlow(StatesGroup):
    choosing = State()

class ConvertFlow(StatesGroup):
    awaiting_file = State()
    awaiting_text = State()

class TranslitFlow(StatesGroup):
    choosing_dir = State()
    awaiting_text = State()

class PaymentFlow(StatesGroup):
    choosing_kind = State()
    choosing_plan = State()
    awaiting_proof = State()
