import asyncio
import os
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.types import InputMediaVideo, Message

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

app = Client(
    "cover_changer",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

user_thumbs: dict[int, str] = {}
media_groups: dict[str, list] = defaultdict(list)
media_group_tasks: dict[str, asyncio.Task] = {}


@app.on_message(filters.command("start") & filters.private)
async def start(client: Client, message: Message):
    await message.reply(
        "👋 **Video Cover Changer Bot**\n\n"
        "1️⃣ Send a **photo** → sets as cover\n"
        "2️⃣ Send **video(s)** → cover changes in seconds!\n\n"
        "✅ No re-upload · ✅ Caption same · ✅ Order same"
    )


# ── Save Cover Photo ──────────────────────────────────────────
@app.on_message(filters.photo & filters.private)
async def save_cover(client: Client, message: Message):
    user_id = message.from_user.id

    old = user_thumbs.get(user_id)
    if old and os.path.exists(old):
        try:
            os.remove(old)
        except Exception:
            pass

    msg = await message.reply("⬇️ Downloading cover...")
    path = await client.download_media(message, file_name=f"thumb_{user_id}.jpg")
    user_thumbs[user_id] = path
    await msg.edit("✅ **Cover saved!** Now send your video(s).")


# ── Single Video ──────────────────────────────────────────────
@app.on_message(filters.video & filters.private)
async def handle_video(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id not in user_thumbs:
        await message.reply("⚠️ Send a **photo** first to set as cover!")
        return

    if message.media_group_id:
        group_id = message.media_group_id
        media_groups[group_id].append(message)

        if group_id in media_group_tasks:
            media_group_tasks[group_id].cancel()

        task = asyncio.create_task(process_group(client, group_id, user_id))
        media_group_tasks[group_id] = task
    else:
        await process_single(client, message, user_id)


# ── Process Single ────────────────────────────────────────────
async def process_single(client: Client, message: Message, user_id: int):
    thumb_path = user_thumbs.get(user_id)
    if not thumb_path or not os.path.exists(thumb_path):
        await message.reply("⚠️ Cover not found. Send photo again.")
        return

    status = await message.reply("⚡ Changing cover...")

    try:
        # Step 1: Copy message instantly (file_id reuse, no download)
        copied = await message.copy(chat_id=message.chat.id)

        # Step 2: Edit only the thumbnail (only thumb uploads, ~seconds)
        await client.edit_message_media(
            chat_id=message.chat.id,
            message_id=copied.id,
            media=InputMediaVideo(
                media=message.video.file_id,   # original file_id reused
                thumb=thumb_path,
                caption=message.caption or "",
                caption_entities=message.caption_entities,
                supports_streaming=True,
            ),
        )

        await status.edit("✅ Cover changed!")

    except Exception as e:
        await status.edit(f"❌ Error: `{e}`")


# ── Process Media Group ───────────────────────────────────────
async def process_group(client: Client, group_id: str, user_id: int):
    await asyncio.sleep(2)  # collect all group messages

    messages = sorted(media_groups.pop(group_id, []), key=lambda m: m.id)
    media_group_tasks.pop(group_id, None)

    if not messages:
        return

    thumb_path = user_thumbs.get(user_id)
    if not thumb_path or not os.path.exists(thumb_path):
        await messages[0].reply("⚠️ Cover not found. Send photo again.")
        return

    status = await messages[0].reply(f"⚡ Changing cover for **{len(messages)}** video(s)...")

    try:
        # Step 1: Copy entire media group instantly
        copied_msgs = await client.copy_media_group(
            chat_id=messages[0].chat.id,
            from_chat_id=messages[0].chat.id,
            message_id=messages[0].id,
        )

        # Sort copied messages to maintain order
        copied_msgs = sorted(copied_msgs, key=lambda m: m.id)

        # Step 2: Edit each message's thumbnail only
        for orig, copied in zip(messages, copied_msgs):
            await client.edit_message_media(
                chat_id=orig.chat.id,
                message_id=copied.id,
                media=InputMediaVideo(
                    media=orig.video.file_id,   # original file_id reused
                    thumb=thumb_path,
                    caption=orig.caption or "",
                    caption_entities=orig.caption_entities,
                    supports_streaming=True,
                ),
            )

        await status.edit(f"✅ Cover changed for **{len(messages)}** video(s)!")

    except Exception as e:
        await status.edit(f"❌ Error: `{e}`")


print("Bot started...")
app.run()
