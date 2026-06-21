from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import batch_confirm_keyboard, categories_keyboard, expense_accounts_keyboard
from src.bot.states import BatchExpenseStates
from src.domain.schemas import ExpenseDraft
from src.repositories import account_repo, category_repo, user_repo
from src.services import balance_service
from src.services.category_learning import category_label, offer_remember_rule, save_learned_rule
from src.services.transaction_service import filter_spendable_accounts, record_expense, resolve_category_id

logger = logging.getLogger(__name__)

router = Router()


def format_batch_preview(drafts: list[dict]) -> str:
    lines = [f"Нашёл {len(drafts)} транзакций:"]
    for idx, draft in enumerate(drafts, start=1):
        merchant = draft.get("merchant") or "—"
        amount = draft.get("amount", "?")
        currency = draft.get("currency", "")
        cat = category_label(draft.get("category_slug"))
        date_str = ""
        if draft.get("transaction_date"):
            raw = draft["transaction_date"]
            if isinstance(raw, str):
                date_str = f" — {date.fromisoformat(raw).strftime('%d.%m')}"
            else:
                date_str = f" — {raw.strftime('%d.%m')}"
        lines.append(f"{idx}. {merchant} — {amount} {currency} — {cat}{date_str}")
    return "\n".join(lines)


async def start_batch_expense_flow(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    drafts: list[ExpenseDraft],
    *,
    raw_json: str | None = None,
) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=message.from_user.id)
    await category_repo.ensure_system_categories(session)

    payload = [d.model_dump(mode="json") for d in drafts]
    await state.update_data(
        batch_drafts=payload,
        batch_raw=raw_json,
        telegram_id=message.from_user.id,
        from_photo=True,
    )
    await message.answer(format_batch_preview(payload))

    accounts = await account_repo.list_accounts(session, user.id)
    spendable = filter_spendable_accounts(accounts)
    if not spendable:
        await message.answer("Сначала добавь счёт: /add_account")
        await state.clear()
        return

    await state.set_state(BatchExpenseStates.waiting_account)
    await message.answer(
        "С какого счёта списать все операции?",
        reply_markup=expense_accounts_keyboard(accounts, None, prefix="batch_account"),
    )


async def _show_batch_confirm(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    drafts = data["batch_drafts"]
    account_name = data.get("account_name", "")
    text = format_batch_preview(drafts)
    if account_name:
        text += f"\n\nСчёт: {account_name}"
    text += "\n\nСохранить все?"
    await state.set_state(BatchExpenseStates.confirm)
    await message.answer(text, reply_markup=batch_confirm_keyboard(len(drafts)))


@router.callback_query(BatchExpenseStates.waiting_account, F.data.startswith("batch_account:"))
async def process_batch_account(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    if callback.data.endswith(":all"):
        accounts = await account_repo.list_accounts(session, user.id)
        spendable = filter_spendable_accounts(accounts)
        await callback.message.edit_text("Выбери счёт:")
        await callback.message.edit_reply_markup(
            reply_markup=expense_accounts_keyboard(spendable, None, prefix="batch_account"),
        )
        await callback.answer()
        return

    account_id = int(callback.data.split(":")[1])
    account = await account_repo.get_account_by_id(session, user.id, account_id)
    if not account:
        await callback.answer("Счёт не найден", show_alert=True)
        return

    await state.update_data(account_id=account_id, account_name=account.name)
    await callback.message.edit_text(f"Счёт: {account.name}")
    await callback.answer()
    await _show_batch_confirm(callback.message, state)


@router.callback_query(BatchExpenseStates.confirm, F.data.startswith("batch:edit_cat:"))
async def batch_edit_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    idx = int(callback.data.split(":")[2])
    categories = await category_repo.list_categories(session)
    await state.update_data(editing_index=idx)
    await state.set_state(BatchExpenseStates.waiting_category_fix)
    await callback.message.answer(
        f"Категория для #{idx + 1}:",
        reply_markup=categories_keyboard(categories, prefix=f"batch_cat:{idx}"),
    )
    await callback.answer()


@router.callback_query(BatchExpenseStates.waiting_category_fix, F.data.startswith("batch_cat:"))
async def batch_set_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    _, idx_str, slug = callback.data.split(":", 2)
    idx = int(idx_str)
    data = await state.get_data()
    drafts = data["batch_drafts"]
    if idx >= len(drafts):
        await callback.answer("Позиция не найдена", show_alert=True)
        return

    old_slug = drafts[idx].get("category_slug")
    drafts[idx]["category_slug"] = slug
    merchant = drafts[idx].get("merchant")
    await state.update_data(batch_drafts=drafts)
    await callback.message.edit_text(f"#{idx + 1}: {category_label(slug)}")
    await callback.answer()

    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    if slug != old_slug and merchant:
        await offer_remember_rule(callback.message, session, user.id, merchant, slug)

    await _show_batch_confirm(callback.message, state)


@router.callback_query(BatchExpenseStates.confirm, F.data == "batch:save")
async def batch_save(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user, actor = await user_repo.resolve_data_and_actor(session, telegram_id=callback.from_user.id)
    data = await state.get_data()
    drafts = data["batch_drafts"]
    account_id = data["account_id"]
    raw_input = data.get("batch_raw")

    missing_cat = [i for i, d in enumerate(drafts) if not d.get("category_slug")]
    if missing_cat:
        await callback.answer("Укажи категорию для всех позиций", show_alert=True)
        return

    saved = 0
    account = None
    try:
        for draft in drafts:
            amount = Decimal(str(draft["amount"]))
            currency = draft["currency"]
            category_id = await resolve_category_id(session, draft.get("category_slug"))
            transaction_date = None
            if draft.get("transaction_date"):
                raw_date = draft["transaction_date"]
                transaction_date = date.fromisoformat(raw_date) if isinstance(raw_date, str) else raw_date

            _, account = await record_expense(
                session,
                user.id,
                account_id,
                amount,
                currency,
                actor_user_id=actor.id,
                category_id=category_id,
                merchant=draft.get("merchant"),
                transaction_date=transaction_date,
                source_message_id=callback.message.message_id,
                raw_input=raw_input,
                source_type="photo",
            )
            saved += 1
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    except Exception:
        logger.exception("Failed to save batch expenses for user %s", user.id)
        await callback.answer("Не удалось сохранить пакет. Попробуй ещё раз.", show_alert=True)
        return

    await state.clear()
    balance_line = ""
    if account:
        balance_line = f"\nБаланс {account.name}: {balance_service.format_money(account.balance, account.currency)}"
    await callback.message.edit_text(f"Записал {saved} операций ✅{balance_line}", parse_mode=None)
    await callback.answer()


@router.callback_query(F.data == "batch:cancel")
async def batch_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@router.callback_query(F.data.startswith("learn:"))
async def handle_learn_rule(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if callback.data == "learn:no":
        await callback.message.edit_text("Ок, не запоминаю.")
        await callback.answer()
        return

    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer()
        return
    pattern = parts[2]
    category_slug = parts[3]
    user = await user_repo.get_or_create_user(session, telegram_id=callback.from_user.id)
    await save_learned_rule(session, user.id, pattern, category_slug)
    await callback.message.edit_text(f"Запомнил: {pattern} → {category_label(category_slug)}")
    await callback.answer()
