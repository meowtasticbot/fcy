import asyncio
import importlib

from pyrogram import Client, idle
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import NoActiveGroupCall

import config
from Clonify import LOGGER, app, userbot
from Clonify.core.call import PRO
from Clonify.misc import sudo
from Clonify.plugins import ALL_MODULES
from Clonify.utils.database import clonebotdb, get_banned_users, get_gbanned
from config import BANNED_USERS
from Clonify.plugins.tools.clone import restart_bots


async def _load_clone_assistant_string():
    me = await app.get_me()
    bot_data = clonebotdb.find_one({"bot_id": me.id}) or {}
    db_string = (bot_data.get("string_session") or "").strip()

    if db_string:
        config.STRING1 = db_string


def _rebuild_assistant_clients():
    userbot.one = Client(
        name="PROAss1",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        session_string=str(config.STRING1),
        no_updates=True,
    )
    PRO.userbot1 = Client(
        name="RAUSHANAss1",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        session_string=str(config.STRING1),
    )
    PRO.one = PyTgCalls(
        PRO.userbot1,
        cache_duration=150,
    )


async def init():
    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await app.start()
    await _load_clone_assistant_string()

    if not config.STRING1:
        LOGGER(__name__).error("String Session not filled, please provide a valid session.")
        exit()

    _rebuild_assistant_clients()
    for all_module in ALL_MODULES:
        importlib.import_module("Clonify.plugins" + all_module)
    LOGGER("Clonify.plugins").info("𝐀𝐥𝐥 𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬 𝐋𝐨𝐚𝐝𝐞𝐝 𝐁𝐚𝐛𝐲🥳...")
    await userbot.start()
    await PRO.start()
    try:
        await PRO.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("Clonify").error(
            "𝗣𝗹𝗭 𝗦𝗧𝗔𝗥𝗧 𝗬𝗢𝗨𝗥 𝗟𝗢𝗚 𝗚𝗥𝗢𝗨𝗣 𝗩𝗢𝗜𝗖𝗘𝗖𝗛𝗔𝗧\𝗖𝗛𝗔𝗡𝗡𝗘𝗟\n\n𝗠𝗨𝗦𝗜𝗖 𝗕𝗢𝗧 𝗦𝗧𝗢𝗣........"
        )
        exit()
    except:
        pass
    await PRO.decorators()
    await restart_bots()
    LOGGER("Clonify").info(
        "╔═════ஜ۩۞۩ஜ════╗\n  ☠︎︎𝗠𝗔𝗗𝗘 𝗕𝗬 𝗣𝗿𝗼𝗕𝗼t𝘀☠︎︎\n╚═════ஜ۩۞۩ஜ════╝"
    )
    await idle()
    await app.stop()
    await userbot.stop()
    LOGGER("Clonify").info("𝗦𝗧𝗢𝗣 𝗠𝗨𝗦𝗜𝗖🎻 𝗕𝗢𝗧..")
