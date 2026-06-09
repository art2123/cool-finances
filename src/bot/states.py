from aiogram.fsm.state import State, StatesGroup


class AddAccountStates(StatesGroup):
    name = State()
    currency = State()
    balance = State()
    account_type = State()


class EditAccountStates(StatesGroup):
    waiting_name = State()
    waiting_balance = State()


class ExpenseStates(StatesGroup):
    waiting_amount = State()
    waiting_currency = State()
    waiting_account = State()
    waiting_settlement = State()
    waiting_category = State()
    confirm = State()


class CreditTermsStates(StatesGroup):
    waiting_rate = State()
    waiting_min_payment = State()


class TransferStates(StatesGroup):
    waiting_amount = State()


class ConversionStates(StatesGroup):
    waiting_amount_out = State()
    waiting_amount_in = State()
