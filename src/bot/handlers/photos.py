import base64
import json
from decimal import Decimal

import httpx
from aiogram import F, Router
from aiogram.types import Message

from src.core.config import get_settings
from src.domain.currencies import CURRENCY_PROMPT_CHOICES

router = Router()


@router.message(F.photo)
async def handle_photo(message: Message) -> None:
    settings = get_settings()
    await message.answer("Смотрю изображение...")

    if not settings.openai_api_key:
        await message.answer(
            "OCR требует OPENAI_API_KEY в .env.\n"
            "Пока напиши текстом: «кофе 200 динар»"
        )
        return

    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    downloaded = await message.bot.download_file(file.file_path)
    content = downloaded.read()
    b64 = base64.b64encode(content).decode()

    prompt = (
        'Extract from receipt/screenshot. Return JSON: '
        f'{{"amount": number, "currency": "{CURRENCY_PROMPT_CHOICES}", '
        '"merchant": string, "confidence": 0-1}}'
    )

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }],
                "temperature": 0,
            },
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)

    amount = Decimal(str(data.get("amount", 0)))
    currency = data.get("currency", "RSD")
    merchant = data.get("merchant", "покупка")
    conf = float(data.get("confidence", 0.5))
    suggest = f"{merchant} {amount} {currency}"

    await message.answer(
        f"Распознал ({conf:.0%}):\n{suggest}\n\n"
        f"Напиши для записи: «{suggest}»"
    )
