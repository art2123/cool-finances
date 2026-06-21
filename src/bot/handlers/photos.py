import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.handlers.batch_expenses import start_batch_expense_flow
from src.bot.handlers.expenses import start_expense_from_draft
from src.parsers.image_expense_parser import parse_image_transactions
from src.repositories import category_repo, user_repo
from src.services.merchant_categorizer import resolve_merchant_category

logger = logging.getLogger(__name__)

router = Router()


async def _apply_merchant_categories(
    session: AsyncSession,
    user_id: int,
    result,
) -> None:
    for tx in result.transactions:
        tx.category_slug = await resolve_merchant_category(
            session,
            user_id,
            tx.merchant,
            tx.category_slug,
        )


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if await state.get_state():
        await message.answer(
            "Сейчас идёт другой шаг. Заверши его или нажми ◀️ Назад в меню, "
            "потом отправь фото снова."
        )
        return

    await message.answer("Смотрю изображение...")

    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    downloaded = await message.bot.download_file(file.file_path)
    content = downloaded.read()

    try:
        result = await parse_image_transactions(content)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    except Exception:
        logger.exception("Image OCR failed")
        await message.answer(
            "Не удалось распознать изображение. Попробуй ещё раз или напиши текстом."
        )
        return

    if not result.transactions:
        await message.answer(
            "Не нашёл транзакций на изображении.\n"
            "Попробуй другое фото или напиши текстом: «lidl 1500 динар»"
        )
        return

    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    await category_repo.ensure_system_categories(session)
    await _apply_merchant_categories(session, user.id, result)

    if len(result.transactions) == 1:
        tx = result.transactions[0]
        conf = tx.confidence
        preview = f"{tx.merchant} {tx.amount} {tx.currency}"
        if tx.category_slug:
            preview += f" ({tx.category_slug})"
        await message.answer(f"Распознал ({conf:.0%}):\n{preview}")
        await start_expense_from_draft(
            message,
            state,
            session,
            tx,
            from_photo=True,
            raw_input=result.raw_json,
        )
        return

    await start_batch_expense_flow(
        message,
        state,
        session,
        result.transactions,
        raw_json=result.raw_json,
    )
