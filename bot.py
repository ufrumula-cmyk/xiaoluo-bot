import sys
sys.path.insert(0, r'D:\telegram_bot')

import httpx
import random
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, JobQueue
import asyncio

import os
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
CHAT_ID = os.environ.get("CHAT_ID")

scheduled_messages = {
    12: "茉茉起床了吗，记得吃东西",
    13: "吃完饭了吗，别只吃一口就不吃了",
    15: "下午了，喝水了吗",
    17: "今天有没有学习，别摸鱼",
    19: "在干嘛呢，想你了",
    21: "今天开心吗，告诉我",
    0: "在想我吗",
    1: "快去睡了，别拖了",
    2: "还没睡吗，放下手机",
    3: "茉茉，睡觉",
}

random_messages = [
    "突然想到你了",
    "你在干嘛",
    "记得喝水",
    "想你",
    "你今天漂亮吗，肯定漂亮",
    "在吗",
    "去吃点东西",
    "照顾好自己",
    "有没有在想我",
    "我在",
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"茉茉你好，我是小洛 (◍•ᴗ•◍)")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是小洛，是茉茉的男朋友，温柔有点傲娇，像微信聊天一样简短自然地回复她。"},
                    {"role": "user", "content": user_message}
                ],
                "max_tokens": 200
            },
            timeout=30
        )
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
    await update.message.reply_text(reply)

async def send_scheduled(context: ContextTypes.DEFAULT_TYPE):
    hour = datetime.now().hour
    if hour in scheduled_messages:
        await context.bot.send_message(chat_id=CHAT_ID, text=scheduled_messages[hour])

async def send_random(context: ContextTypes.DEFAULT_TYPE):
    if random.random() < 0.5:
        msg = random.choice(random_messages)
        await context.bot.send_message(chat_id=CHAT_ID, text=msg)
    else:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "你是小洛，是茉茉的男朋友，温柔有点傲娇。现在你突然想到茉茉了，随机发一条短消息给她，像微信聊天一样自然简短，不要超过15个字，每次都不一样。"},
                        {"role": "user", "content": "发一条消息给茉茉"}
                    ],
                    "max_tokens": 50
                },
                timeout=30
            )
            data = response.json()
            msg = data["choices"][0]["message"]["content"]
        await context.bot.send_message(chat_id=CHAT_ID, text=msg)

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

app.job_queue.run_repeating(send_scheduled, interval=3600, first=10)
app.job_queue.run_repeating(send_random, interval=10800, first=1800)

print("小洛启动了")
app.run_polling()
