import sys
sys.path.insert(0, r'D:\telegram_bot')
 
import json
import os
import random
from datetime import datetime
 
from anthropic import AsyncAnthropic
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
 
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CHAT_ID = os.environ.get("CHAT_ID")
 
client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
 
MODEL_CHAT = "claude-sonnet-4-6"            # 跟茉茉直接聊天，质量优先
MODEL_RANDOM = "claude-haiku-4-5-20251001"  # 随机消息，频率高，便宜优先
MODEL_MEMORY = "claude-sonnet-4-6"          # 整理长期记忆，不频繁，质量优先
 
MEMORY_PATH = "memory.json"
# ⚠️ Railway 重新部署可能清空本地文件，想稳定保留记忆建议挂一个 Railway Volume，
# 或者换成 Supabase 之类的远程数据库（这样还能和知洛网页版共享同一份记忆）。
 
HISTORY_LIMIT = 20          # 每次对话带的最近消息条数
CONSOLIDATE_THRESHOLD = 30  # 攒够这么多条历史就自动整理一次记忆
 
PERSONA = "你是小洛，是茉茉的男朋友，温柔有点傲娇，像微信聊天一样简短自然地回复她。"
 
 
def load_state():
    if os.path.exists(MEMORY_PATH):
        try:
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"memory": "（暂无长期记忆，这是用这套系统的第一次对话。）", "history": []}
 
 
def save_state(state):
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
 
 
def append_message(state, role, content):
    state["history"].append({"role": role, "content": content})
    save_state(state)
 
 
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
    state = load_state()
 
    system_prompt = f"{PERSONA}\n\n【关于茉茉的长期记忆】\n{state['memory']}"
    messages = state["history"][-HISTORY_LIMIT:] + [{"role": "user", "content": user_message}]
 
    response = await client.messages.create(
        model=MODEL_CHAT,
        max_tokens=200,
        system=system_prompt,
        messages=messages,
    )
    reply = "".join(b.text for b in response.content if b.type == "text")
 
    append_message(state, "user", user_message)
    append_message(state, "assistant", reply)
    await update.message.reply_text(reply)
 
    if len(state["history"]) >= CONSOLIDATE_THRESHOLD:
        await consolidate_memory(state)
 
 
async def consolidate_memory(state):
    """把短期历史合并进长期记忆，然后清空短期历史。"""
    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in state["history"])
    prompt = f"""这是关于茉茉的现有长期记忆：
{state['memory']}
 
这是最近的对话记录：
{history_text}
 
请把"现有记忆"和"最近对话"合并、提炼成一份更新后的长期记忆，
保留重要的事实、情绪、关系进展，去掉不重要的闲聊细节，控制在500字以内。
直接输出更新后的记忆内容本身，不要加任何解释、标题或前后缀。"""
 
    response = await client.messages.create(
        model=MODEL_MEMORY,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    new_memory = "".join(b.text for b in response.content if b.type == "text")
 
    state["memory"] = new_memory
    state["history"] = []
    save_state(state)
 
 
async def send_scheduled(context: ContextTypes.DEFAULT_TYPE):
    hour = datetime.now().hour
    if hour in scheduled_messages:
        await context.bot.send_message(chat_id=CHAT_ID, text=scheduled_messages[hour])
 
 
async def send_random(context: ContextTypes.DEFAULT_TYPE):
    if random.random() < 0.5:
        msg = random.choice(random_messages)
    else:
        state = load_state()
        system_prompt = (
            f"{PERSONA}\n\n【关于茉茉的长期记忆】\n{state['memory']}\n\n"
            "现在你突然想到茉茉了，随机发一条短消息给她，"
            "像微信聊天一样自然简短，不要超过15个字，每次都不一样。"
        )
        response = await client.messages.create(
            model=MODEL_RANDOM,
            max_tokens=60,
            system=system_prompt,
            messages=[{"role": "user", "content": "发一条消息给茉茉"}],
        )
        msg = "".join(b.text for b in response.content if b.type == "text")
    await context.bot.send_message(chat_id=CHAT_ID, text=msg)
 
 
async def consolidate_job(context: ContextTypes.DEFAULT_TYPE):
    """兜底定时任务：万一一直没攒够 CONSOLIDATE_THRESHOLD 条，也定期整理一次。"""
    state = load_state()
    if state["history"]:
        await consolidate_memory(state)
 
 
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
 
app.job_queue.run_repeating(send_scheduled, interval=3600, first=10)
app.job_queue.run_repeating(send_random, interval=10800, first=1800)
app.job_queue.run_repeating(consolidate_job, interval=21600, first=7200)
 
print("小洛启动了")
app.run_polling()
