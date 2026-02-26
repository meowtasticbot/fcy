import time
from typing import Dict

from pyrogram import Client, filters
from pyrogram.errors import (
    ApiIdInvalid,
    PasswordHashInvalid,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    PhoneNumberInvalid,
    SessionPasswordNeeded,
)
from pyrogram.types import Message

from Clonify.utils.database import clonebotdb
from Clonify.utils.database.clonedb import get_owner_id_from_db
from Clonify.utils.decorators.language import language
from config import OWNER_ID, SUPPORT_CHAT


CONNECT_STATES: Dict[int, dict] = {}


def _is_clone_owner(user_id: int, bot_id: int) -> bool:
    clone_owner = get_owner_id_from_db(bot_id)
    return user_id in [OWNER_ID, clone_owner]


@Client.on_message(filters.command("setstring") & filters.private)
@language
async def set_string_session(client: Client, message: Message, _):
    bot = await client.get_me()
    if not _is_clone_owner(message.from_user.id, bot.id):
        return await message.reply_text("You are not allowed to use this connect flow.")

    if len(message.command) < 2:
        return await message.reply_text("**Usage:** /setstring <session_string>")

    session_string = message.text.split(None, 1)[1].strip()
    clonebotdb.update_one(
        {"bot_id": bot.id},
        {"$set": {"string_session": session_string}},
        upsert=True,
    )
    await message.reply_text("✅ Assistant string saved successfully.")


@Client.on_message(filters.command("disconnect") & filters.private)
@language
async def disconnect_string_session(client: Client, message: Message, _):
    bot = await client.get_me()
    if not _is_clone_owner(message.from_user.id, bot.id):
        return await message.reply_text("You are not allowed to use this connect flow.")

    clonebotdb.update_one(
        {"bot_id": bot.id},
        {"$set": {"string_session": None}},
        upsert=True,
    )
    CONNECT_STATES.pop(message.from_user.id, None)
    await message.reply_text("✅ Assistant disconnected. Saved string removed.")


@Client.on_message(filters.command("transfer") & filters.private)
@language
async def transfer_clone_ownership(client: Client, message: Message, _):
    bot = await client.get_me()
    if not _is_clone_owner(message.from_user.id, bot.id):
        return await message.reply_text("You are not allowed to use this connect flow.")

    new_owner_id = None
    if len(message.command) == 2:
        try:
            new_owner_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("Usage: /transfer <new_owner_id> or reply to a user.")
    elif message.reply_to_message and message.reply_to_message.from_user:
        new_owner_id = message.reply_to_message.from_user.id

    if not new_owner_id:
        return await message.reply_text("Usage: /transfer <new_owner_id> or reply to a user.")

    clonebotdb.update_one(
        {"bot_id": bot.id},
        {"$set": {"user_id": new_owner_id}},
        upsert=False,
    )
    await message.reply_text(f"✅ Ownership transferred to `{new_owner_id}`")


@Client.on_message(filters.command("connect") & filters.private)
@language
async def start_connect_flow(client: Client, message: Message, _):
    bot = await client.get_me()
    if not _is_clone_owner(message.from_user.id, bot.id):
        return await message.reply_text("You are not allowed to use this connect flow.")

    CONNECT_STATES[message.from_user.id] = {
        "step": "api_id",
        "bot_id": bot.id,
    }
    await message.reply_text(
        "**Assistant Connect Started**\n\n"
        "Step 1/5: Send your `API_ID`\n"
        "Send /disconnect any time to clear saved string."
    )


@Client.on_message(filters.private & ~filters.command(["connect", "setstring", "disconnect", "transfer"]))
async def continue_connect_flow(client: Client, message: Message):
    user_id = message.from_user.id
    state = CONNECT_STATES.get(user_id)
    if not state:
        return

    if not message.text:
        return await message.reply_text("Please send text input only for connect steps.")

    bot = await client.get_me()
    if not _is_clone_owner(user_id, bot.id):
        CONNECT_STATES.pop(user_id, None)
        return await message.reply_text("You are not allowed to use this connect flow.")

    step = state.get("step")
    text = (message.text or "").strip()

    if step == "api_id":
        try:
            state["api_id"] = int(text)
        except ValueError:
            return await message.reply_text("Invalid API_ID. Please send numeric API_ID.")
        state["step"] = "api_hash"
        return await message.reply_text("Step 2/5: Send your `API_HASH`")

    if step == "api_hash":
        if len(text) < 10:
            return await message.reply_text("Invalid API_HASH. Send correct value.")
        state["api_hash"] = text
        state["step"] = "phone"
        return await message.reply_text("Step 3/5: Send your phone number with country code (example: +919999999999)")

    if step == "phone":
        state["phone"] = text
        session_name = f"connect_{user_id}_{int(time.time())}"
        temp_client = Client(
            session_name,
            api_id=state["api_id"],
            api_hash=state["api_hash"],
            in_memory=True,
        )
        try:
            await temp_client.connect()
            sent_code = await temp_client.send_code(state["phone"])
        except ApiIdInvalid:
            CONNECT_STATES.pop(user_id, None)
            try:
                await temp_client.disconnect()
            except Exception:
                pass
            return await message.reply_text("Invalid API_ID/API_HASH. Start again with /connect")
        except PhoneNumberInvalid:
            CONNECT_STATES.pop(user_id, None)
            try:
                await temp_client.disconnect()
            except Exception:
                pass
            return await message.reply_text("Invalid phone number. Start again with /connect")
        except Exception as exc:
            CONNECT_STATES.pop(user_id, None)
            try:
                await temp_client.disconnect()
            except Exception:
                pass
            return await message.reply_text(f"Failed to send OTP: {exc}")

        state["temp_client"] = temp_client
        state["phone_code_hash"] = sent_code.phone_code_hash
        state["step"] = "otp"
        return await message.reply_text(
            "Step 4/5: Send OTP code.\n"
            "If Telegram shows `1 2 3 4 5`, send as `12345`."
        )

    if step == "otp":
        otp = text.replace(" ", "")
        temp_client = state["temp_client"]
        try:
            await temp_client.sign_in(
                phone_number=state["phone"],
                phone_code_hash=state["phone_code_hash"],
                phone_code=otp,
            )
            session_string = await temp_client.export_session_string()
            clonebotdb.update_one(
                {"bot_id": bot.id},
                {"$set": {"string_session": session_string}},
                upsert=True,
            )
            try:
                await temp_client.disconnect()
            except Exception:
                pass
            CONNECT_STATES.pop(user_id, None)
            return await message.reply_text("✅ Connected successfully. String session generated and saved.")
        except SessionPasswordNeeded:
            state["step"] = "password"
            return await message.reply_text("Step 5/5: Two-step password enabled. Send your password now.")
        except (PhoneCodeInvalid, PhoneCodeExpired):
            return await message.reply_text("Invalid/expired OTP. Please send OTP again.")
        except Exception as exc:
            try:
                await temp_client.disconnect()
            except Exception:
                pass
            CONNECT_STATES.pop(user_id, None)
            return await message.reply_text(f"Login failed: {exc}")

    if step == "password":
        temp_client = state["temp_client"]
        try:
            await temp_client.check_password(text)
            session_string = await temp_client.export_session_string()
            clonebotdb.update_one(
                {"bot_id": bot.id},
                {"$set": {"string_session": session_string}},
                upsert=True,
            )
            try:
                await temp_client.disconnect()
            except Exception:
                pass
            CONNECT_STATES.pop(user_id, None)
            return await message.reply_text("✅ 2FA verified. String session generated and saved.")
        except PasswordHashInvalid:
            return await message.reply_text("Wrong password. Send your 2FA password again.")
        except Exception as exc:
            try:
                await temp_client.disconnect()
            except Exception:
                pass
            CONNECT_STATES.pop(user_id, None)
            return await message.reply_text(f"2FA verification failed: {exc}")
