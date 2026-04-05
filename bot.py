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


# ── Video Handler ─────────────────────────────────────────────
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


# ── Single Video ──────────────────────────────────────────────
async def process_single(client: Client, message: Message, user_id: int):
    thumb_path = user_thumbs.get(user_id)
    if not thumb_path or not os.path.exists(thumb_path):
        await message.reply("⚠️ Cover not found. Send photo again.")
        return

    status = await message.reply("⚡ Changing cover...")

    try:
        # file_id reuse — only thumb uploads (seconds!)
        await client.send_video(
            chat_id=message.chat.id,
            video=message.video.file_id,
            thumb=thumb_path,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            supports_streaming=True,
        )
        await status.edit("✅ Cover changed!")

    except Exception as e:
        await status.edit(f"❌ Error: `{e}`")


# ── Media Group ───────────────────────────────────────────────
async def process_group(client: Client, group_id: str, user_id: int):
    await asyncio.sleep(2)  # wait for all group msgs

    # Sort by message ID → correct order 1,2,3,4
    messages = sorted(media_groups.pop(group_id, []), key=lambda m: m.id)
    media_group_tasks.pop(group_id, None)

    if not messages:
        return

    thumb_path = user_thumbs.get(user_id)
    if not thumb_path or not os.path.exists(thumb_path):
        await messages[0].reply("⚠️ Cover not found. Send photo again.")
        return

    status = await messages[0].reply(
        f"⚡ Changing cover for **{len(messages)}** video(s)..."
    )

    try:
        media_list = []
        for msg in messages:
            media_list.append(
                InputMediaVideo(
                    media=msg.video.file_id,   # reuse file_id, no download
                    thumb=thumb_path,
                    caption=msg.caption or "",
                    caption_entities=msg.caption_entities,
                    supports_streaming=True,
                )
            )

        # Send in chunks of 10 (Telegram limit)
        for i in range(0, len(media_list), 10):
            chunk = media_list[i:i + 10]
            await client.send_media_group(
                chat_id=messages[0].chat.id,
                media=chunk,
            )

        await status.edit(f"✅ Done! **{len(messages)}** video(s) cover changed!")

    except Exception as e:
        await status.edit(f"❌ Error: `{e}`")


print("Bot started...")
app.run()
