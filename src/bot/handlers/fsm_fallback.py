from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

router = Router()


@router.message()
async def unhandled_fsm_message(message: Message, state: FSMContext) -> None:
    """Срабатывает только если ни один другой хендлер не ответил."""
    if not await state.get_state():
        return
    await message.answer(
        "Не понял это сообщение. Введи текст по подсказке выше "
        "или начни заново через меню (◀️ Назад → нужный раздел)."
    )
