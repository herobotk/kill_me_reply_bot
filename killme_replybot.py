import os
import re
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta # <-- ✅ Added
from collections import defaultdict  # <-- ✅ Added
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from humanize import naturalsize
# ============ CONFIG ============
# Stores latest user message data with timestamp
user_messages = {}

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Read group/channel IDs from environment
def get_id_list(env_name):
    return [int(x.strip()) for x in os.getenv(env_name, "").split(",") if x.strip()]

KILLME_CHANNELS = get_id_list("KILLME_CHANNELS")
REPLYBOT_GROUP = get_id_list("REPLYBOT_GROUP")
GROUP_EXCLUDED_IDS = get_id_list("GROUP_EXCLUDED_IDS")  # Only user IDs

user_messages = {}

# ============ Health Check ============

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is alive!')

threading.Thread(target=lambda: HTTPServer(("", 8080), HealthHandler).serve_forever(), daemon=True).start()

# ============ Filename Cleaner ============

def clean_filename(filename: str) -> str:
    keep_username = "@movie_talk_backup"
    filename = filename.replace(keep_username, "KEEP__USERNAME")

    filename = re.sub(r'@\w+', '', filename)
    filename = re.sub(r'https?://\S+|www\.\S+|\S+\.(com|in|net|org|me|info)', '', filename)
    filename = re.sub(r't\.me/\S+', '', filename)
    filename = re.sub(r'[^\w\s.\-()_]', '', filename)
    filename = re.sub(r'\s{2,}', ' ', filename).strip()

    return filename.replace("KEEP__USERNAME", keep_username)

# ============ Caption Builder ============

def generate_caption(file_name, file_size):
    cleaned_name = clean_filename(file_name)
    return f"""{cleaned_name}
⚙️ 𝚂𝚒𝚣𝚎 ~ [{file_size}]
⚜️ 𝙿𝚘𝚜𝚝 𝚋𝚢 ~ 𝐌𝐎𝐕𝐈𝐄 𝐓𝐀𝐋𝐊

⚡𝖩𝗈𝗂𝗇 Us ~ ❤️
➦『 @movie_talk_backup 』"""

# ============ Bot Setup ============

bot = Client("killme_replybot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ============ Private Commands ============

@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(_, message: Message):
    await message.reply("👋 Bot is alive! ReplyBot & KillMe logic activated.")

@bot.on_message(filters.private & filters.command("help"))
async def help_cmd(_, message: Message):
    await message.reply_text(
        "📌 Bot Commands:\n"
        "/start – Start\n"
        "/help – Help\n\n"
        "✅ Group: ReplyBot active\n"
        "✅ Channels: KillMe bot (mention/domain cleaner)",
        disable_web_page_preview=True
    )

# ============ Channel Handler (Kill Me Bot) ============

@bot.on_message(filters.channel & ~filters.me)
async def channel_handler(_, message: Message):
    if message.chat.id not in KILLME_CHANNELS:
        return

    media = message.document or message.video or message.audio
    original_caption = message.caption or ""

    if media and media.file_name:
        file_name = media.file_name
        file_size = naturalsize(media.file_size)
        caption = generate_caption(file_name, file_size)
    else:
        caption = clean_filename(original_caption)

    try:
        await message.copy(chat_id=message.chat.id, caption=caption)
        await message.delete()
    except FloodWait as e:
        await asyncio.sleep(e.value)
        try:
            await message.copy(chat_id=message.chat.id, caption=caption)
            await message.delete()
        except Exception as e2:
            print(f"[Retry Error] {e2}")
    except Exception as e:
        print(f"[Channel Error] {e}")

# ============ Group Handler (Reply Bot) ============

@bot.on_message(filters.group & filters.text & ~filters.regex(r"^/"))
async def group_reply_handler(_, message: Message):
    if message.chat.id not in REPLYBOT_GROUP:
        return

    if message.sender_chat and message.sender_chat.id == message.chat.id:
        return

    if message.from_user and message.from_user.id in GROUP_EXCLUDED_IDS:
        return

    user = message.from_user
    if not user:
        return

    uid = user.id
    text = message.text.strip()
    now = datetime.utcnow()

    current = user_messages.get(uid)

    if current:
        # Compare message text and time
        if current["text"] == text and now - current["time"] < timedelta(minutes=60):
            try:
                await bot.delete_messages(message.chat.id, current["bot_msg_id"])
            except:
                pass
            sent = await message.reply_text("ᴀʟʀᴇᴀᴅʏ ɴᴏᴛᴇᴅ ✅\nᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ⏳...")
        else:
            sent = await message.reply_text("ʀᴇQᴜᴇꜱᴛ ʀᴇᴄᴇɪᴠᴇᴅ✅\nᴜᴘʟᴏᴀᴅ ꜱᴏᴏɴ... ᴄʜɪʟʟ✨")
    else:
        sent = await message.reply_text("ʀᴇQᴜᴇꜱᴛ ʀᴇᴄᴇɪᴠᴇᴅ✅\nᴜᴘʟᴏᴀᴅ ꜱᴏᴏɴ... ᴄʜɪʟʟ✨")

    user_messages[uid] = {"text": text, "bot_msg_id": sent.id, "time": now}

# ============ SV Save Handler (Admin Feature) ============
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio

@bot.on_message(filters.group & filters.reply & filters.regex(r"^(?i)sv$"))
async def save_filter_handler(_, message: Message):
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status.lower() not in ["administrator", "creator"]:
            return

        if not message.reply_to_message:
            return

        user_msg = message.reply_to_message

        if user_msg.from_user and (user_msg.from_user.is_bot or user_msg.from_user.id == message.from_user.id):
            return

        await message.delete()

        photo_url = "https://ibb.co/DHvHzcyR"
        caption = (
            "Dᴀᴛᴀʙᴀsᴇ Uᴘᴅᴀᴛᴇᴅ ✅\n"
            "Sᴇᴀʀᴄʜ ɪɴ Gʀᴏᴜᴘ..🔎\n"
            "(Cʟɪᴄᴋ ᴛʜᴇ Bᴇʟᴏᴡ Bᴜᴛᴛᴏɴ👇)"
        )

        group_username = message.chat.username
        btn_url = f"https://t.me/{group_username}" if group_username else "https://t.me/"

        buttons = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Sᴇᴀʀᴄʜ Hᴇʀᴇ", url=btn_url)]]
        )

        await user_msg.reply_photo(photo=photo_url, caption=caption, reply_markup=buttons)

        temp_msg = await message.reply_text("✅ Saved Successfully Boss!")
        await asyncio.sleep(3)
        await temp_msg.delete()

    except Exception as e:
        print(f"[SV Handler Error] {e}")

# ============ Run ============

bot.run()
