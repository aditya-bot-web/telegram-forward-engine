import asyncio
import os
import time
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from flask import Flask

# 🔐 ENV variables (Railway से आएँगे)
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

client = TelegramClient("bot", api_id, api_hash).start(bot_token=bot_token)
@client.on(events.NewMessage(pattern="/start"))
async def start(event):
    await event.reply("✅ Bot is running successfully!")

# 🔄 dynamic channel map
CHANNEL_MAP = {}
@client.on(events.NewMessage(pattern="/add"))
async def add_cmd(e):
    try:
        _, src, tgt = e.text.split()
        CHANNEL_MAP[int(src)] = int(tgt)
        await e.reply(f"✅ Added\n{src} → {tgt}")
    except:
        await e.reply("❌ Use: /add source target")

@client.on(events.NewMessage(pattern="/list"))
async def list_cmd(e):
    if not CHANNEL_MAP:
        await e.reply("Empty ❌")
    else:
        msg = "\n".join([f"{s} → {t}" for s, t in CHANNEL_MAP.items()])
        await e.reply(msg)

@client.on(events.NewMessage(pattern="/remove"))
async def remove_cmd(e):
    try:
        _, src = e.text.split()
        CHANNEL_MAP.pop(int(src))
        await e.reply(f"❌ Removed {src}")
    except:
        await e.reply("Error")
# 📊 stats
stats = {
    "count": 0,
    "start_time": time.time(),
    "delay": 5,
    "running": True
}

LAST_ID_FILE = "last_ids.txt"

# 🧠 load/save ids
def load_ids():
    if os.path.exists(LAST_ID_FILE):
        with open(LAST_ID_FILE, "r") as f:
            return eval(f.read())
    return {}

def save_ids(data):
    with open(LAST_ID_FILE, "w") as f:
        f.write(str(data))

# 🌐 keep-alive server (Railway sleep avoid)
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Running 🚀"

def run_web():
    app.run(host="0.0.0.0", port=3000)

# ⚙️ safe forward
async def safe_forward(msg, target, delay):
    while True:
        try:
            await msg.forward_to(target)
            return delay

        except FloodWaitError as e:
            wait = e.seconds
            print(f"FloodWait {wait}s")
            await asyncio.sleep(wait)
            delay = min(delay + 2, 20)

        except Exception as e:
            print(e)
            await asyncio.sleep(5)

# 🔁 process old messages
async def process_channel(source, target, saved_ids):
    delay = 5
    last_id = saved_ids.get(str(source), 0)

    async for msg in client.iter_messages(source, min_id=last_id, reverse=True):

        if not stats["running"]:
            await asyncio.sleep(2)
            continue

        if msg and not msg.action:
            delay = await safe_forward(msg, target, delay)

            saved_ids[str(source)] = msg.id
            save_ids(saved_ids)

            stats["count"] += 1
            stats["delay"] = delay

            print(f"{source} → {msg.id}")

            await asyncio.sleep(delay)

# ⚡ live messages
@client.on(events.NewMessage)
async def live(event):
    src = event.chat_id

    if src in CHANNEL_MAP and stats["running"]:
        tgt = CHANNEL_MAP[src]

        try:
            await event.message.forward_to(tgt)
            stats["count"] += 1
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)

# 🎮 COMMANDS

@client.on(events.NewMessage(pattern='/start_forward'))
async def start_cmd(e):
    stats["running"] = True
    await e.reply("✅ STARTED")

@client.on(events.NewMessage(pattern='/stop_forward'))
async def stop_cmd(e):
    stats["running"] = False
    await e.reply("⛔ STOPPED")

@client.on(events.NewMessage(pattern='/status'))
async def status_cmd(e):
    await e.reply("RUNNING" if stats["running"] else "STOPPED")

@client.on(events.NewMessage(pattern='/progress'))
async def progress_cmd(e):
    await e.reply(f"Forwarded: {stats['count']}")

@client.on(events.NewMessage(pattern='/speed'))
async def speed_cmd(e):
    elapsed = time.time() - stats["start_time"]
    speed = stats["count"] / elapsed if elapsed else 0
    await e.reply(f"Speed: {round(speed,2)} msg/sec")

@client.on(events.NewMessage(pattern='/delay'))
async def delay_cmd(e):
    await e.reply(f"Delay: {stats['delay']} sec")

@client.on(events.NewMessage(pattern='/add'))
async def add_cmd(e):
    try:
        _, src, tgt = e.text.split()
        CHANNEL_MAP[int(src)] = int(tgt)
        await e.reply("Added ✅")
    except:
        await e.reply("Error ❌")

@client.on(events.NewMessage(pattern='/remove'))
async def remove_cmd(e):
    try:
        _, src = e.text.split()
        CHANNEL_MAP.pop(int(src), None)
        await e.reply("Removed ❌")
    except:
        await e.reply("Error")

@client.on(events.NewMessage(pattern='/list'))
async def list_cmd(e):
    txt = "\n".join([f"{s} → {t}" for s,t in CHANNEL_MAP.items()])
    await e.reply(txt or "Empty")

# 🚀 main
async def main():
    await client.start()

    saved_ids = load_ids()

    tasks = []
    for s,t in CHANNEL_MAP.items():
        tasks.append(process_channel(s,t,saved_ids))

    await asyncio.gather(*tasks)

# 🧠 run both bot + web
import threading
threading.Thread(target=run_web).start()
client.loop.run_until_complete(main())
client.run_until_disconnected()
