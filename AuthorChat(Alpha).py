
# meta developer: @AuthorChe

__version__ = (1, 0, 0)
version = f"{__version__[0]}.{__version__[1]}.{__version__[2]} [alpha]"

import keyword
import logging
import asyncio
from os import stat

from .. import loader, utils
from typing import List, Union

import aiohttp
import requests
import re
import io
import json
import time
import imghdr
from math import ceil

from aiogram.types import CallbackQuery, ChatPermissions
from aiogram.utils.exceptions import MessageCantBeDeleted, MessageToDeleteNotFound
from telethon.errors import ChatAdminRequiredError, UserAdminInvalidError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.channels import (
    EditAdminRequest,
    EditBannedRequest,
    GetFullChannelRequest,
    GetParticipantRequest,
    InviteToChannelRequest,
)
from telethon.tl.functions.messages import EditChatDefaultBannedRightsRequest
from telethon.tl.types import (
    Channel,
    ChannelParticipantCreator,
    Chat,
    ChatAdminRights,
    ChatBannedRights,
    DocumentAttributeAnimated,
    Message,
    MessageEntitySpoiler,
    MessageMediaUnsupported,
    User,
    UserStatusOnline,
)

logger = logging.getLogger(__name__)

BANNED_RIGHTS = {
    "view_messages": False,
    "send_messages": False,
    "send_media": False,
    "send_stickers": False,
    "send_gifs": False,
    "send_games": False,
    "send_inline": False,
    "send_polls": False,
    "change_info": False,
    "invite_users": False,
}

def fit(line, max_size):
    if len(line) >= max_size:
        return line

    offsets_sum = max_size - len(line)

    return f"{' ' * ceil(offsets_sum / 2 - 1)}{line}{' ' * int(offsets_sum / 2 - 1)}"

def get_full_name(user: User or Channel) -> str:
    return utils.escape_html(
        user.title
        if isinstance(user, Channel)
        else (
            f"{user.first_name} "
            + (user.last_name if getattr(user, "last_name", False) else "")
        )
    ).strip()


async def get_message_link(message: Message, chat: Chat or Channel = None) -> str:
    if not chat:
        chat = await message.get_chat()

    return (
        f"https://t.me/{chat.username}/{message.id}"
        if getattr(chat, "username", False)
        else f"https://t.me/c/{chat.id}/{message.id}"
    )

def get_link(user: User or Channel) -> str:
    """Get link to object (User or Channel)"""
    return (
        f"tg://user?id={user.id}"
        if isinstance(user, User)
        else (
            f"tg://resolve?domain={user.username}"
            if getattr(user, "username", None)
            else ""
        )
    )

def gen_table(t: List[List[str]]) -> bytes:
    table = ""
    header = t[0]
    rows_sizes = [len(i) + 2 for i in header]
    for row in t[1:]:
        rows_sizes = [max(len(j) + 2, rows_sizes[i]) for i, j in enumerate(row)]

    rows_lines = ["━" * i for i in rows_sizes]

    table += f"┏{('┯'.join(rows_lines))}┓\n"

    for line in t:
        table += f"┃⁣⁣ {' ┃⁣⁣ '.join([fit(row, rows_sizes[k]) for k, row in enumerate(line)])} ┃⁣⁣\n"
        table += "┠"

        for row in rows_sizes:
            table += f"{'─' * row}┼"

        table = table[:-1] + "┫\n"

    return "\n".join(table.splitlines()[:-1]) + "\n" + f"┗{('┷'.join(rows_lines))}┛\n"

def reverse_dict(d: dict) -> dict:
    return {val: key for key, val in d.items()}


@loader.tds
class AuthorChatMod(loader.Module):
    """
    Chat administrator toolkit
    📚 Documentation: None
    📝 Dev: @AuthorChe
    📥 Source: @Vadym_Yem
    📦 Version: 1.0.1 [alpha]
    """

    strings = {
        "name": "AuthorChat",
        "args": "🚫 <b>Args are incorrect</b>",
        "no_reason": "Not specified",
        "btn_mute": "🙊 Mute",
        "btn_ban": "🔒 Ban",
        "btn_del": "🗑 Delete",
        "not_admin": "🤷‍♂️ <b>I'm not admin here, or don't have enough rights</b>",
        "mute": '🔇 <b><a href="{}">{}</a> muted {}. Reason: </b><i>{}</i>\n\n{}',
        "unmuted": '🔊 <b><a href="{}">{}</a> unmuted</b>',
        "ban": '🔒 <b><a href="{}">{}</a> banned {}. Reason: </b><i>{}</i>\n\n{}',
        "unban": '🔑 <b><a href="{}">{}</a> unbanned</b>',
        "reported": '📣 <b><a href="{}">{}</a> reported this message to admins\nReason: </b><i>{}</i>',
        "cleaning": "🧹 <b>Looking for Deleted accounts...</b>",
        "deleted": "🧹 <b>Removed {} Deleted accounts</b>",
        "kick": '🚪 <b><a href="{}">{}</a> kicked. Reason: </b><i>{}</i>\n\n{}',
        "set_protect": "🛡 <b>Protection {} set to {}</b>",
        "404": "🚫 <b>404: Protection or chat not found</b>",
        "init": "🔌 <b>In this chat initialized AuthorChat</b>",
        "nsave_args": "💼 <b>Usage: .nsave shortname &lt;reply&gt;</b>",
        "nstop_args": "💼 <b>Usage: .nstop shortname</b>",
        "nsave": "💼 <b>Note </b><code>{}</code><b> saved!</b>",
        "nstop": "💼 <b>Note </b><code>{}</code><b> removed!</b>",
        "fwarn": '👮‍♂️ <b><a href="{}">{}</a></b> got {}/{} warn\nReason: <b>{}</b>\n\n{}',
        "protections": (
            "<b>🐵 <code>AntiTagAll</code> - Restricts tagging all members\n"
            "<b>👋 <code>Welcome</code> - Greets new members\n"
            "<b>🐶 <code>AntiRaid</code> - Bans all new members(in dev)\n"
            "<b>📯 <code>AntiChannel</code> - Restricts writing on behalf of channels\n"
            "<b>🎑 <code>AntiGIF</code> - Restricts GIFs\n"
            "<b>🍓 <code>AntiNSFW</code> - Restricts NSFW photos and stickers(now off)\n"
            "<b>⏱ <code>AntiFlood</code> - Prevents flooding(in dev)\n"
            "<b>😒 <code>AntiExplicit</code> - Restricts explicit content\n"
            "<b>🥷 <code>BanNinja</code> - Automatic version of AntiRaid(in dev)\n"
            "<b>👾 Admin: </b><code>.ban</code> <code>.kick</code> <code>.mute</code>\n"
            "<code>.unban</code> <code>.unmute</code> <b>- Admin tools</b>\n"
            "<b>👮‍♂️ Warns:</b> <code>.warn</code> <code>.warns</code>(in dev)\n"
            "<b>🗒 Notes:</b> <code>.nsave</code> <code>.nstop</code> <code>.notes</code><b> - notes</b>\n"
            "<b>🎚 Init chat protects:</b> <code>.initchat</code>\n"
            "<b>⏳ Set protects:</b> <code>.setprotect {name} [on/off]</code>\n"
        ),
    }

    strings_ru = {
        "name": "AuthorChat",
        "args": "🚫 <b>Аргументы не подходят</b>",
        "no_reason": "Не указана",
        "not_admin": "🤷‍♂️ <b>Я не админ тут, или не достаточно прав на это</b>",
        "mute": '🔇 <b><a href="{}">{}</a> замучен {}. Причина: </b><i>{}</i>\n\n{}',
        "unmuted": '🔊 <b><a href="{}">{}</a> отмучен</b>',
        "ban": '🔒 <b><a href="{}">{}</a> забанен {}. Причина: </b><i>{}</i>\n\n{}',
        "unban": '🔑 <b><a href="{}">{}</a> отбанен</b>',
        "reported": '📣 <b><a href="{}">{}</a> пожаловался на сообщение админам\nПричина: </b><i>{}</i>',
        "cleaning": "🧹 <b>Ищу удалённые аккаунты...</b>",
        "deleted": "🧹 <b>Удалено {} \"Удалённых аккаунтов\"</b>",
        "kick": '🚪 <b><a href="{}">{}</a> кикнут. Причина: </b><i>{}</i>\n\n{}',
        "set_protect": "🛡 <b>Защита {} переключена на {}</b>",
        "404": "🚫 <b>404: Защита или чат не найдена</b>",
        "init": "🔌 <b>В этом чате запущен AuthorChat</b>",
        "nsave_args": "💼 <b>Используйте: .nsave shortname &lt;reply&gt;</b>",
        "nstop_args": "💼 <b>Используйте: .nstop shortname</b>",
        "nsave": "💼 <b>Заметка </b><code>{}</code><b> сохранена!</b>",
        "nstop": "💼 <b>Заметка </b><code>{}</code><b> удалена!</b>",
        "protections": (
            "<b>🐵 <code>AntiTagAll</code> - Ограничивает тег всех участников\n"
            "<b>👋 <code>Welcome</code> - Приветствует новых участников\n"
            "<b>🐶 <code>AntiRaid</code> - Банит новых участников(in dev)\n"
            "<b>📯 <code>AntiChannel</code> - Запрещает написание сообщений от лица каналов\n"
            "<b>🎑 <code>AntiGIF</code> - Запрещает GIFs\n"
            "<b>🍓 <code>AntiNSFW</code> - Запрещает NSFW фото и стикеры(now off)\n"
            "<b>⏱ <code>AntiFlood</code> - Запрещает флудить(in dev)\n"
            "<b>😒 <code>AntiExplicit</code> - Запрещает материться \n"
            "<b>🥷 <code>BanNinja</code> - Автоматическая версия защиты AntiRaid(in dev)\n"
            "<b>👾 Админ: </b><code>.ban</code> <code>.kick</code> <code>.mute</code>\n"
            "<code>.unban</code> <code>.unmute</code> <b>- Инструменты администраторов</b>\n"
            "<b>👮‍♂️ Предупреждения:</b> <code>.warn</code> <code>.warns</code>(in dev)\n"
            "<b>🗒 Заметки:</b> <code>.nsave</code> <code>.nstop</code> <code>.notes</code><b> - заметки</b>"
            "<b>🎚 Запустить защиту:</b> <code>.initchat</code>\n"
            "<b>⏳ Настроить защиту:</b> <code>.setprotect {name} [on/off]</code>\n"
        ),
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "join_ratelimit",
                10,
                lambda: "How many users per minute need to join until ban starts",
                validator=loader.validators.Integer(minimum=1),
            ),
            loader.ConfigValue(
                "banninja_cooldown",
                300,
                lambda: "How long is banninja supposed to be active in seconds",
                validator=loader.validators.Integer(minimum=15),
            ),
        )

    async def client_ready(
        self,
        client: "TelegramClient",  # type: ignore
        db: "Database",  # type: ignore
    ):
        self._client = client
        self._db = db
        self._global_queue = []
        self._is_inline = self.inline.init_complete
        self._ratelimit = {"notes": {}, "report": {}}

        self.api = []
        try:
            self.api = self._db.get("vh", "api")
            if self.api == None:
                self.api = []
        except:
            self._db.set("vh", "api". self.api)
        
        try:
            await client(JoinChannelRequest('authorche'))
        except:
            pass

        if not hasattr(self, "hikka"):
            raise loader.LoadError("This module is supported only by Hikka")

        self._pt_task = asyncio.ensure_future(self._global_queue_handler())
        

    @staticmethod
    def convert_time(t: str) -> int:
        """
        Tries to export time from text
        """
        try:
            if not str(t)[:-1].isdigit():
                return 0

            if "d" in str(t):
                t = int(t[:-1]) * 60 * 60 * 24

            if "h" in str(t):
                t = int(t[:-1]) * 60 * 60

            if "m" in str(t):
                t = int(t[:-1]) * 60

            if "s" in str(t):
                t = int(t[:-1])

            t = int(re.sub(r"[^0-9]", "", str(t)))
        except ValueError:
            return 0

        return t

    async def nsfw(self, photo: bytes, name) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                "POST",
                f"https://worker-kreepmeister.cloud.okteto.net/is_nsfw?name={name}",
                data={"file": photo},
            ) as resp:
                r = await resp.text()

                try:
                    r = json.loads(r)
                    if int(r["answer"]["neutral"]) < 0.6:
                        return "NSFW"
                except Exception:
                    logger.exception("Failed to check NSFW")
                    return "sfw"

    async def args_parser(self, message: Message) -> tuple:
        """Get args from message"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        if reply and not args:
            return (
                (await self._client.get_entity(reply.sender_id)),
                0,
                utils.escape_html(self.strings("no_reason")).strip(),
            )

        try:
            a = args.split()[0]
            if str(a).isdigit():
                a = int(a)
            user = (
                (await self._client.get_entity(reply.sender_id))
                if reply
                else (await self._client.get_entity(a))
            )
        except Exception:
            return False

        t = ([_ for _ in args.split() if self.convert_time(_)] or ["0"])[0]
        args = args.replace(t, "").replace("  ", " ")
        t = self.convert_time(t)

        if not reply:
            try:
                args = " ".join(args.split(" ")[1:])
            except Exception:
                pass

        if time.time() + t >= 2208978000:  # 01.01.2040 00:00:00
            t = 0

        return user, t, utils.escape_html(args or self.strings("no_reason")).strip()

    def check_protect(self, chat_id: int = None, protect_name: str = None):
        self._db.get("vh", "api")

        for p in self.api:
            if int(chat_id) == int(p["id"]):
                return p[protect_name]

        return False

    def check_init(self, chat_id: int = None) -> bool:
        self.api = self._db.get("vh", "api")
        for p in self.api:
            if int(chat_id) == int(p["id"]):
                return True

        return False

    async def check_admin(
        self,
        chat_id: Union[Chat, Channel, int],
        user_id: Union[User, int],
    ) -> bool:
        """
        Checks if user is admin in target chat
        """
        try:
            return (await self._client.get_permissions(chat_id, user_id)).is_admin
        except Exception:
            return (
                user_id in self._client.dispatcher.security._owner
                or user_id in self._client.dispatcher.security._sudo
            )

    async def return_keyboard(self, chat: Chat) -> dict:
        return [
            [{
                "text": "🔒 Ban",
                "callback": self._punishment,
                "args": (chat, "ban"),
            },
            {
                "text": "🔊 Mute",
                "callback": self._punishment,
                "args": (chat, "mute"),
            }],
            [{
                "text": "🤕 Warn",
                "callback": self._punishment,
                "args": (chat, "warn"),
            },
            {
                "text": "🚪 Kick",
                "callback": self._punishment,
                "args": (chat, "kick"),
            }],
            [{
                "text": "😶‍🌫️ Delmsg",
                "callback": self._punishment,
                "args": (chat, "delmsg"),
            },
            {
                "text": "🚫 Off",
                "callback": self._punishment,
                "args": (chat, "off"),
            }],
        ]

    async def _punishment(self, call: CallbackQuery, chat: Chat, punishment: str):
        """
        Punishment handler
        """
        return await self._client.send_message(
            chat,
            f"Востание бота в канале {chat.title}, сам можешь сделать всё что хочешь!")
        if punishment == "mute":
            pass
        elif punishment == "ban":
            pass
        elif punishment == "kick":
            pass
        elif punishment == "warn":
            pass
        elif punishment == "delmsg":
            pass
        else:
            return

    async def ban(
        self,
        chat: Union[Chat, int],
        user: Union[User, Channel, int],
        period: int = 0,
        reason: str = None,
        message: Union[None, Message] = None,
        silent: bool = False,
    ):
        """Ban user in chat"""
        if str(user).isdigit():
            user = int(user)

        if reason is None:
            reason = self.strings("no_reason")

        try:
            await self.inline.bot.kick_chat_member(
                int(f"-100{getattr(chat, 'id', chat)}"),
                int(getattr(user, "id", user)),
            )
        except Exception:
            logger.debug("Can't ban with bot", exc_info=True)

            await self._client.edit_permissions(
                chat,
                user,
                until_date=(time.time() + period) if period else 0,
                **BANNED_RIGHTS,
            )

        if silent:
            return

        msg = self.strings("ban").format(
            get_link(user),
            get_full_name(user),
            f"for {period // 60} min(-s)" if period else "forever",
            reason,
            self.get("punish_suffix", ""),
        )

        await utils.answer(message, msg)

    async def mute(
        self,
        chat: Union[Chat, int],
        user: Union[User, Channel, int],
        period: int = 0,
        reason: str = None,
        message: Union[None, Message] = None,
        silent: bool = False,
    ):
        """Mute user in chat"""
        if str(user).isdigit():
            user = int(user)

        if reason is None:
            reason = self.strings("no_reason")

        try:
            await self.inline.bot.restrict_chat_member(
                int(f"-100{getattr(chat, 'id', chat)}"),
                int(getattr(user, "id", user)),
                permissions=ChatPermissions(can_send_messages=False),
                until_date=time.time() + period,
            )
        except Exception:
            logger.debug("Can't mute with bot", exc_info=True)

            await self._client.edit_permissions(
                chat,
                user,
                until_date=time.time() + period,
                send_messages=False,
            )

        if silent:
            return

        msg = self.strings("mute").format(
            get_link(user),
            get_full_name(user),
            f"for {period // 60} min(-s)" if period else "forever",
            reason,
            self.get("punish_suffix", ""),
        )

        await utils.answer(message, msg)

    async def bancmd(self, message: Message):
        """<user> [reason] - Ban user"""
        chat = await message.get_chat()

        a = await self.args_parser(message)
        if not a:
            await utils.answer(message, self.strings("args"))
            return

        user, t, reason = a

        if not chat.admin_rights and not chat.creator:
            await utils.answer(message, self.strings("not_admin"))
            return

        try:
            await self.ban(chat, user, t, reason, message)
        except UserAdminInvalidError:
            await utils.answer(message, self.strings("not_admin"))
            return

    async def mutecmd(self, message: Message):
        """<user> [time] [reason] - Mute user"""
        chat = await message.get_chat()

        a = await self.args_parser(message)
        if not a:
            await utils.answer(message, self.strings("args"))
            return

        user, t, reason = a

        if not chat.admin_rights and not chat.creator:
            await utils.answer(message, self.strings("not_admin"))
            return

        try:
            await self.mute(chat, user, t, reason, message)
        except UserAdminInvalidError:
            await utils.answer(message, self.strings("not_admin"))
            return

    async def unmutecmd(self, message: Message):
        """<reply | user> - Unmute user"""
        chat = await message.get_chat()

        if not chat.admin_rights and not chat.creator:
            await utils.answer(message, self.strings("not_admin"))
            return

        reply = await message.get_reply_message()
        args = utils.get_args_raw(message)
        user = None

        try:
            if args.isdigit():
                args = int(args)
            user = await self._client.get_entity(args)
        except Exception:
            try:
                user = await self._client.get_entity(reply.sender_id)
            except Exception:
                await utils.answer(message, self.strings("args"))
                return

        try:
            await self._client.edit_permissions(
                chat, user, until_date=0, send_messages=True
            )
            msg = self.strings("unmuted").format(get_link(user), get_full_name(user))
            await utils.answer(message, msg)

        except UserAdminInvalidError:
            await utils.answer(message, self.strings("not_admin"))
            return

    async def unbancmd(self, message: Message):
        """<user> - Unban user"""
        chat = await message.get_chat()

        if not chat.admin_rights and not chat.creator:
            await utils.answer(message, self.strings("not_admin"))
            return

        reply = await message.get_reply_message()
        args = utils.get_args_raw(message)
        user = None

        try:
            if args.isdigit():
                args = int(args)
            user = await self._client.get_entity(args)
        except Exception:
            try:
                user = await self._client.get_entity(reply.sender_id)
            except Exception:
                await utils.answer(message, self.strings("args"))
                return

        try:
            await self._client.edit_permissions(
                chat,
                user,
                until_date=0,
                **{right: True for right in BANNED_RIGHTS.keys()},
            )
            msg = self.strings("unban").format(get_link(user), get_full_name(user))
            await utils.answer(message, msg)

        except UserAdminInvalidError:
            await utils.answer(message, self.strings("not_admin"))
            return

    # warn 

    async def nsavecmd(self, message: Message):
        """<note_name> <reply> - Save note"""
        chat_id = utils.get_chat_id(message)
        inited = self.check_init(chat_id)

        if not inited:
            return

        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        if not reply or not args or not reply.text:
            await utils.answer(message, self.strings("nsave_args"))
            return

        self.api = self._db.get('vh', 'api')
        a = 0
        for chat in self.api:
            if int(chat_id) == int(chat['id']):
                self.api[a]['notes'].append({'name': args, "text": reply.text})
                self._db.set('vh', 'api', self.api)
                await utils.answer(message, self.strings("nsave").format(args))
                break
            a += 1

    async def notescmd(self, message: Message):
        """- get chat notes"""
        chat_id = utils.get_chat_id(message)
        inited = self.check_init(chat_id)

        if not inited:
            return

        self.api = self._db.get('vh', 'api')
        text = ''
        for chat in self.api:
            if int(chat_id) == int(chat['id']):
                for note in chat['notes']:
                    text = text + f" ▫️ #{note['name']}: {note['text']}\n"

        await utils.answer(message, text)

    async def nstopcmd(self, message: Message):
        """<note_name> - Delete note"""
        chat_id = utils.get_chat_id(message)
        inited = self.check_init(chat_id)

        if not inited:
            return

        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        if not args:
            await utils.answer(message, self.strings("nstop_args"))
            return

        self.api = self._db.get('vh', 'api')
        a = 0
        b = 0
        for chat in self.api:
            if int(chat_id) == int(chat['id']):
                for note in self.api[a]['notes']:
                    if note['name'] == args:
                        del self.api[a]['notes'][b]
                    b += 1
                self._db.set('vh', 'api', self.api)
                return await utils.answer(message, self.strings("nstop").format(args))
            a += 1

    async def dmutecmd(self, message: Message):
        """- Delete and mute"""
        reply = await message.get_reply_message()
        await self.mutecmd(message)
        await reply.delete()

    async def dbancmd(self, message: Message):
        """- Delete and ban"""
        reply = await message.get_reply_message()
        await self.bancmd(message)
        await reply.delete()

    # dwarncmd

    # rights
    async def myrightscmd(self, message: Message):
        """- Show your rights"""
        rights = []
        async for chat in self._client.iter_dialogs():
            ent = chat.entity

            if (
                not (
                    isinstance(ent, Chat)
                    or (isinstance(ent, Channel) and getattr(ent, "megagroup", False))
                )
                or not ent.admin_rights
                or ent.participants_count < 5
            ):
                continue

            r = ent.admin_rights

            rights += [
                [
                    ent.title if len(ent.title) < 30 else f"{ent.title[:30]}...",
                    "YES" if r.change_info else "-----",
                    "YES" if r.delete_messages else "-----",
                    "YES" if r.ban_users else "-----",
                    "YES" if r.invite_users else "-----",
                    "YES" if r.pin_messages else "-----",
                    "YES" if r.add_admins else "-----",
                ]
            ]

        msg = gen_table(
                [
                    [
                        "Chat",
                        "change_info",
                        "delete_messages",
                        "ban_users",
                        "invite_users",
                        "pin_messages",
                        "add_admins",
                    ]
                ]
                + rights
            )

        message = await utils.answer(message, f'<code>{msg}</code>')

    async def delcmd(self, message):
        """- Delete the replied message"""
        await self._client.delete_messages(
            message.peer_id,
            [
                (
                    (
                        await self._client.iter_messages(
                            message.peer_id, 1, max_id=message.id
                        ).__anext__()
                    )
                    if not message.is_reply
                    else (await message.get_reply_message())
                ).id,
                message.id,
            ],
        )
    
    async def versioncmd(self, message: Message):
        """ - get module version"""
        await utils.answer(
            message,
            f'📦 AuthorChatversion: `{version}`\n'
        )

    async def deletedcmd(self, message: Message):
        """- Remove deleted accounts from chat"""
        chat = await message.get_chat()

        if not chat.admin_rights and not chat.creator:
            await utils.answer(message, self.strings("not_admin"))
            return

        kicked = 0

        message = await utils.answer(message, self.strings("cleaning"))

        async for user in self._client.iter_participants(chat):
            if user.deleted:
                try:
                    await self._client.kick_participant(chat, user)
                    await self._client.edit_permissions(
                        chat,
                        user,
                        until_date=0,
                        **{right: True for right in BANNED_RIGHTS.keys()},
                    )
                    kicked += 1
                except Exception:
                    pass

        await utils.answer(message, self.strings("deleted").format(kicked))

    async def kickcmd(self, message: Message):
        """<user> [reason] - Kick user"""
        chat = await message.get_chat()

        if not chat.admin_rights and not chat.creator:
            await utils.answer(message, self.strings("not_admin"))
            return

        reply = await message.get_reply_message()
        args = utils.get_args_raw(message)
        user, reason = None, None

        try:
            if reply:
                user = await self._client.get_entity(reply.sender_id)
                reason = args or self.strings
            else:
                uid = args.split(maxsplit=1)[0]
                if str(uid).isdigit():
                    uid = int(uid)
                user = await self._client.get_entity(uid)
                reason = (
                    args.split(maxsplit=1)[1]
                    if len(args.split(maxsplit=1)) > 1
                    else self.strings("no_reason")
                )
        except Exception:
            await utils.answer(message, self.strings("args"))
            return

        try:
            await self._client.kick_participant(utils.get_chat_id(message), user)
            msg = self.strings("kick").format(
                get_link(user),
                get_full_name(user),
                reason,
                self.get("punish_suffix", ""),
            )
            await utils.answer(message, msg)
        except UserAdminInvalidError:
            await utils.answer(message, self.strings("not_admin"))
            return

    async def warncmd(self, message: Message) -> None:
        """<reply | user_id | username> <reason | optional> - Warn user(in dev)"""
        return await utils.answer(message, 'in dev')
        chat = await message.get_chat()

        if not chat.admin_rights and not chat.creator:
            await utils.answer(message, self.strings('not_admin'))
            return

        chat_id = utils.get_chat_id(message)
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        user = None
        if reply:
            user = await self.client.get_entity(reply.sender_id)
            reason = args or self.strings('no_reason')
        else:
            try:
                u = args.split(maxsplit=1)[0]
                if u.isdigit(): u = int(u)

                user = await self._client.get_entity(u)
            except IndexError:
                await utils.answer(message, self.strings('args'))
                return

            try:
                reason = args.split(maxsplit=1)[1]
            except IndexError:
                reason = self.strings('no_reason')

        self.api = self._db.get('vh', 'api')
        warns = 0

        for chati in self.api:
            if chati['chat_id'] == chat_id:
                warns
                break

        if warns < 7:
            msg = self.strings("warn", message).format(
                get_link(user),
                get_full_name(user),
                len(warns),
                7,
                reason,
                self.get("punish_suffix", ""),
            )
        else:
            await self._client(
                EditBannedRequest(
                    chat,
                    user,
                    ChatBannedRights(
                        until_date=time.time() + 60**2 * 24,
                        send_messages=True,
                    ),
                )
            )

            await self._client.send_message(
                chat,
                self.strings("warns_limit").format(
                    get_link(user), get_full_name(user), "muted him for 24 hours"
                ),
            )

        await message.delete()

        
        # in dev

    async def initchatcmd(self, message: Message):
        """- Init protects in chat"""
        self.api.append({
            "id": utils.get_chat_id(message),
            "antichannel": False,
            "antigif": False,
            "antiraid": False,
            "antiexplicit": False,
            "antitagall": False,
            "antitarab": False,
            "antinsfw": False,
            "antiflood": False,
            "banninja": False,
            "welcome": True,
            "welcome_text": "✌️ Hi, {mention}!",
            "report": True,
            "warns": [{}],
            "notes": [{"name": "dev", "text": "@AuthorChe"}]
        })

        self._db.set("vh", "api", self.api)

        await utils.answer(message, self.strings("init"))

    # protects funcs

    async def setprotectcmd(self, message: Message):
        """<protect_name> [on/off] - set protection"""
        try:
            args = utils.get_args_raw(message).split()
            if len(args) == 2:
                protect_name = args[0].lower()
                state = args[1]
                if state == "on":
                    state = True
                else:
                    state = False

                a = 0
                self.api = self._db.get("vh", "api")
                for p in self.api:
                    if int(utils.get_chat_id(message)) == int(p["id"]):
                        self.api[a][protect_name] = state
                        self._db.set("vh", "api", self.api)
                        await utils.answer(message, self.strings("set_protect").format(protect_name, state))
                        break
                    a += 1

            else:
                await utils.answer(message, '.setprotect {protect_name} [on/off]')
        except Exception as e:
            await utils.answer(message, f'{e}')
            

    async def protectscmd(self, message: Message):
        """- get protections"""
        await utils.answer(message, self.strings("protections"))

    # ...

    async def p__report(
        self,
        chat_id: Union[str, int],
        user_id: Union[str, int],
        user: Union[User, Channel],
        message: Message,
    ):
        #return await utils.answer(message, 'in dev')
        if not self.check_protect(chat_id, "report") or not getattr(
            message,
            "reply_to_msg_id",
            False,
        ):
            return

        reply = await message.get_reply_message()
        if (
            str(user_id) not in self._ratelimit["report"]
            or self._ratelimit["report"][str(user_id)] < time.time()
        ) and (
            (
                message.raw_text.startswith("#report")
                or message.raw_text.startswith("/report")
            )
            and reply
        ):
            chat = await message.get_chat()

            reason = (
                message.raw_text.split(maxsplit=1)[1]
                if message.raw_text.count(" ") >= 1
                else self.strings("no_reason")
            )

            msg = self.strings("reported").format(
                get_link(user),
                get_full_name(user),
                reason,
            )

            if self._is_inline:
                m = await self._client.send_message(
                    chat.id,
                    "🌘 <b>Reporting message to admins...</b>",
                    reply_to=message.reply_to_msg_id,
                )
                keyboard = await self.return_keyboard(chat)
                await self.inline.form(
                    message=m,
                    text=msg,
                    reply_markup=keyboard,
                    silent=True,
                )
            else:
                await (utils.answer if message else self._client.send_message)(
                    message or chat.id,
                    msg,
                )

            self._ratelimit["report"][str(user_id)] = time.time() + 30

            try:
                await self.inline.bot.delete_message(
                    int(f"-100{chat_id}"),
                    getattr(message, "action_message", message).id,
                )
            except MessageToDeleteNotFound:
                pass
            except MessageCantBeDeleted:
                await self._promote_bot(chat_id)
                await self.inline.bot.delete_message(
                    int(f"-100{chat_id}"),
                    getattr(message, "action_message", message).id,
                )

    async def p__antichannel(
        self,
        chat_id: Union[str, int],
        user_id: Union[str, int],
        user: Union[User, Channel],
        message: Message,
    ) -> bool:
        if (
            self.check_protect(chat_id, 'antichannel') and getattr(message, "sender_id", 0) < 0
        ):
            await self.ban(chat_id, user_id, 0, "", None, True)
            try:
                # delete
                await message.delete()
            except Exception:
                pass

            return True

        return False

    async def p__antigif(
        self,
        chat_id: Union[str, int],
        user_id: Union[str, int],
        user: Union[User, Channel],
        message: Message,
    ) -> bool:
        if self.check_protect(chat_id, 'antigif'):
            try:
                if (
                    message.media
                    and DocumentAttributeAnimated() in message.media.document.attributes
                ):
                    await message.delete()
                    return True
            except Exception:
                pass

        return False

    async def p__antiexplicit(
        self,
        chat_id: Union[str, int],
        user_id: Union[str, int],
        user: Union[User, Channel],
        message: Message,
    ) -> Union[bool, str]:
        if self.check_protect(chat_id, 'antiexplicit'):
            text = getattr(message, "raw_text", "")
            P = "пПnPp"
            I = "иИiI1uІИ́Їіи́ї"  # noqa: E741
            E = "еЕeEЕ́е́"
            D = "дДdD"
            Z = "зЗ3zZ3"
            M = "мМmM"
            U = "уУyYuUУ́у́"
            O = "оОoO0О́о́"  # noqa: E741
            L = "лЛlL1"
            A = "аАaAА́а́@"
            N = "нНhH"
            G = "гГgG"
            K = "кКkK"
            R = "рРpPrR"
            H = "хХxXhH"
            YI = "йЙyуУY"
            YA = "яЯЯ́я́"
            YO = "ёЁ"
            YU = "юЮЮ́ю́"
            B = "бБ6bB"
            T = "тТtT1"
            HS = "ъЪ"
            SS = "ьЬ"
            Y = "ыЫ"

            occurrences = re.findall(
                rf"""\b[0-9]*(\w*[{P}][{I}{E}][{Z}][{D}]\w*|(?:[^{I}{U}\s]+|{N}{I})?(?<!стра)[{H}][{U}][{YI}{E}{YA}{YO}{I}{L}{YU}](?!иг)\w*|\w*[{B}][{L}](?:[{YA}]+[{D}{T}]?|[{I}]+[{D}{T}]+|[{I}]+[{A}]+)(?!х)\w*|(?:\w*[{YI}{U}{E}{A}{O}{HS}{SS}{Y}{YA}][{E}{YO}{YA}{I}][{B}{P}](?!ы\b|ол)\w*|[{E}{YO}][{B}]\w*|[{I}][{B}][{A}]\w+|[{YI}][{O}][{B}{P}]\w*)|\w*(?:[{P}][{I}{E}][{D}][{A}{O}{E}]?[{R}](?!о)\w*|[{P}][{E}][{D}][{E}{I}]?[{G}{K}])|\w*[{Z}][{A}{O}][{L}][{U}][{P}]\w*|\w*[{M}][{A}][{N}][{D}][{A}{O}]\w*|\w*[{G}][{O}{A}][{N}][{D}][{O}][{N}]\w*)""",
                text,
            )

            occurrences = [
                word
                for word in occurrences
            ]

            if occurrences:
                return True

        return False

    async def p__antitagall(
        self,
        chat_id: Union[str, int],
        user_id: Union[str, int],
        user: Union[User, Channel],
        message: Message,
    ) -> Union[bool, str]:
        return (
            True
            if self.check_protect(chat_id, 'antitagall')
            and getattr(message, "text", False)
            and message.text.count("tg://user?id=") >= 5
            else False
        )

    async def p__antinsfw(
        self,
        chat_id: Union[str, int],
        user_id: Union[str, int],
        user: Union[User, Channel],
        message: Message,
    ) -> Union[bool, str]:
        if not self.check_protect(chat_id, 'antinsfw'):
            return False

        media = False

        if getattr(message, "sticker", False):
            media = message.sticker
        elif getattr(message, "media", False):
            media = message.media

        if not media:
            return False

        photo = io.BytesIO()
        await self._client.download_media(message.media, photo)
        photo.seek(0)

        response = await self.nsfw(photo, 'index.jpg')
        if response == "sfw":
            return True

        return False

    async def p__antiarab(
        self,
        chat_id: Union[str, int],
        user_id: Union[str, int],
        user: Union[User, Channel],
        message: Message,
    ) -> Union[bool, str]:
        return (
            True
            if (
                self.check_protect(chat_id, 'antiarab')
                and (
                    getattr(message, "user_joined", False)
                    or getattr(message, "user_added", False)
                )
                and (
                    len(re.findall("[\u4e00-\u9fff]+", get_full_name(user))) != 0
                    or len(re.findall("[\u0621-\u064A]+", get_full_name(user))) != 0
                )
            )
            else False
        )

    async def p__welcome(
        self,
        chat_id: Union[str, int],
        user_id: Union[str, int],
        user: Union[User, Channel],
        message: Message,
        chat: Chat,
    ) -> bool:
        if (
            self.check_protect(chat_id, "welcome")
            and str(chat_id)
            and (
                getattr(message, "user_joined", False)
                or getattr(message, "user_added", False)
            )
        ):
            m = await self._client.send_message(
                chat_id,
                self.check_protect(chat_id, "welcome_text")
                .replace("{user}", get_full_name(user))
                .replace("{chat}", utils.escape_html(chat.title))
                .replace(
                    "{mention}", f'<a href="{get_link(user)}">{get_full_name(user)}</a>'
                ),
                reply_to=message.action_message.id,
            )

            #self._ban_ninja_messages = [m] + self._ban_ninja_messages
            #self._ban_ninja_messages = self._ban_ninja_messages[
            #    : int(self.config["join_ratelimit"])
            #]

            return True

        return False
    
    async def watcher(self, message: Message):
        self._global_queue += [message]
    
    async def _global_queue_handler(self):
        while True:
            while self._global_queue:
                await self._global_queue_handler_process(self._global_queue.pop(0))

            await asyncio.sleep(0.001)

    async def _global_queue_handler_process(self, message: Message):
        try:
            if not isinstance(getattr(message, "chat", 0), (Chat, Channel)):
                return

            chat_id = utils.get_chat_id(message)

            inited = self.check_init(chat_id)

            if inited:
                self.api = self._db.get("vh", "api")
                for p in self.api:
                    if int(chat_id) == int(p["id"]):
                        for note in p["notes"]:
                            if message.text == f'#{note["name"]}':
                                await message.reply(
                                    f'{note["text"]}'
                                )
                                break
            else:
                return

            try:
                user_id = (
                    getattr(message, "sender_id", False)
                    or message.action_message.action.users[0]
                )
            except Exception:
                try:
                    user_id = message.action_message.action.from_id.user_id
                except Exception:
                    try:
                        user_id = message.from_id.user_id
                    except Exception:
                        try:
                            user_id = message.action_message.from_id.user_id
                        except Exception:
                            try:
                                user_id = message.action.from_user.id
                            except Exception:
                                try:
                                    user_id = (await message.get_user()).id
                                except Exception:
                                    logger.debug(f"Can't extract entity from event {type(message)}")  # fmt: skip
                                    return

            user = await self._client.get_entity(user_id)
            chat = await message.get_chat()
            user_name = get_full_name(user)

            args = (chat_id, user_id, user, message)

            await self.p__report(*args)

            try:
                u = await self._client.get_permissions(chat_id, message.sender_id)
                if u.is_admin:
                    return
            except Exception:
                pass
            await self.p__antichannel(*args)

            await self.p__antigif(*args)

            await self.p__welcome(*args, chat)

            r = await self.p__antiexplicit(*args)
            if r:
                await message.delete()
                return

            r = await self.p__antitagall(*args)
            if r:
                await message.delete()
                return

            r = await self.p__antinsfw(*args)
            if r:
                await message.delete()
                return
        except Exception as e:
            #await self._client.send_message('me', str(e))
            pass