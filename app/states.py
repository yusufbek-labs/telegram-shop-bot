from aiogram.fsm.state import State, StatesGroup


class Checkout(StatesGroup):
    name = State()
    phone = State()
    address = State()
    payment = State()
    confirm = State()


class AddProduct(StatesGroup):
    category = State()
    name = State()
    price = State()
    description = State()
    image = State()
    confirm = State()


class EditProduct(StatesGroup):
    field = State()
    value = State()


class Broadcast(StatesGroup):
    text = State()
    confirm = State()
