#  ZeldrisRobot
#  Copyright (C) 2017-2019, Paul Larsen
#  Copyright (C) 2022, IDNCoderX Team, <https://github.com/IDN-C-X/ZeldrisRobot>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.


import ast
import csv
import json
import os
import re
import time
import uuid
from io import BytesIO
from typing import Optional

from telegram import (
    ParseMode,
    Chat,
    User,
    MessageEntity,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatAction,
    Update,
)
from telegram.error import BadRequest, TelegramError, Unauthorized
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from telegram.utils.helpers import mention_html, mention_markdown

import zeldris.modules.sql.feds_sql as sql
from zeldris import (
    dispatcher,
    OWNER_ID,
    DEV_USERS,
    WHITELIST_USERS,
    MESSAGE_DUMP,
    LOGGER,
)
from zeldris.modules.disable import DisableAbleCommandHandler
from zeldris.modules.helper_funcs.alternate import (
    send_message,
    typing_action,
    send_action,
)
from zeldris.modules.helper_funcs.chat_status import is_user_admin
from zeldris.modules.helper_funcs.extraction import (
    extract_user,
    extract_unt_fedban,
    extract_user_fban,
)
from zeldris.modules.helper_funcs.string_handling import markdown_parser

# Hello bot owner, I spended for feds many hours of my life, Please don't remove this if you still respect MrYacha
# and peaktogoo and AyraHikari too Federation by MrYacha 2018-2019 Federation rework by Mizukito Akito 2019
# Federation update v2 by Ayra Hikari 2019
#
# Time spended on feds = 10h by #MrYacha
# Time spended on reworking on the whole feds = 22+ hours by @peaktogoo
# Time spended on updating version to v2 = 26+ hours by @AyraHikari
#
# Total spended for making this features is 68+ hours

# LOGGER.info("Original federation module by MrYacha, reworked by Mizukito Akito (@peaktogoo) on Telegram.")

# TODO: Fix Loads of code duplication

FBAN_ERRORS = {
    "User is an administrator of the chat",
    "Chat not found",
    "Not enough rights to restrict/unrestrict chat member",
    "User_not_participant",
    "Peer_id_invalid",
    "Group chat was deactivated",
    "Need to be inviter of a user to kick it from a basic group",
    "Chat_admin_required",
    "Only the creator of a basic group can kick group administrators",
    "Channel_private",
    "Not in the chat",
    "Have no rights to send a message",
}

UNFBAN_ERRORS = {
    "User is an administrator of the chat",
    "Chat not found",
    "Not enough rights to restrict/unrestrict chat member",
    "User_not_participant",
    "Method is available for supergroup and channel chats only",
    "Not in the chat",
    "Channel_private",
    "Chat_admin_required",
    "Have no rights to send a message",
}


@typing_action
def new_fed(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message
    if chat.type != "private":
        update.effective_message.reply_text(
            "You can your federation in my PM, not in a group."
        )
        return
    fednam = message.text.split(None, 1)
    if len(fednam) >= 2:
        fednam = fednam[1]
        fed_id = str(uuid.uuid4())
        fed_name = fednam
        LOGGER.info(fed_id)

        # Currently only for creator
        # if fednam == 'Team Nusantara Disciplinary Circle':
        # fed_id = "TeamNusantaraDevs"

        x = sql.new_fed(user.id, fed_name, fed_id)
        if not x:
            update.effective_message.reply_text(
                "Can't federate! Please contact my owner @starryboi if the problem persists."
            )
            return

        update.effective_message.reply_text(
            "*You have successfully created a new federation!*"
            "\nName: `{}`"
            "\nID: `{}`"
            "\n\nUse the command below to join the federation:"
            "\n`/joinfed {}`".format(fed_name, fed_id, fed_id),
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            context.bot.send_message(
                MESSAGE_DUMP,
                "Federation <b>{}</b> has been created with ID: <pre>{}</pre>".format(
                    fed_name, fed_id
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            LOGGER.warning("Cannot send a message to MESSAGE_DUMP")
    else:
        update.effective_message.reply_text(
            "Please write down the name of the federation"
        )


@typing_action
def del_fed(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    args = context.args
    if chat.type != "private":
        update.effective_message.reply_text(
            "You can delete your federation in my PM, not in the group."
        )
        return
    if args:
        is_fed_id = args[0]
        getinfo = sql.get_fed_info(is_fed_id)
        if not getinfo:
            update.effective_message.reply_text("This federation is not found")
            return
        if int(getinfo["owner"]) == int(user.id) or int(user.id) == OWNER_ID:
            fed_id = is_fed_id
        else:
            update.effective_message.reply_text("Only federation owners can do this!")
            return
    else:
        update.effective_message.reply_text("What should I delete?")
        return

    if is_user_fed_owner(fed_id, user.id):
        update.effective_message.reply_text(
            "Are you sure you want to delete your federation? This action cannot be canceled, you will lose your "
            "entire "
            "ban list, and '{}' will be permanently lost.".format(getinfo["fname"]),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="⚠️ Remove Federation ⚠️",
                            callback_data="rmfed_{}".format(fed_id),
                        )
                    ],
                    [InlineKeyboardButton(text="Cancel", callback_data="rmfed_cancel")],
                ]
            ),
        )
        return

    update.effective_message.reply_text("Only federation owners can do this!")


@typing_action
def fed_chat(update, _):
    chat = update.effective_chat
    fed_id = sql.get_fed_id(chat.id)

    user_id = update.effective_message.from_user.id
    if not is_user_admin(update.effective_chat, user_id):
        update.effective_message.reply_text(
            "You must be an admin to execute this command"
        )
        return

    if not fed_id:
        update.effective_message.reply_text("This group is not in any federation!")
        return

    chat = update.effective_chat
    info = sql.get_fed_info(fed_id)

    text = "This chat is part of the following federation:"
    text += "\n{} (ID: <code>{}</code>)".format(info["fname"], fed_id)

    update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


@typing_action
def join_fed(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM!",
        )
        return

    message = update.effective_message
    administrators = chat.get_administrators()
    fed_id = sql.get_fed_id(chat.id)
    args = context.args

    if user.id not in DEV_USERS:
        for admin in administrators:
            status = admin.status
            if status == "creator" and str(admin.user.id) != str(user.id):
                update.effective_message.reply_text(
                    "Only group creators can use this command!"
                )
                return
    if fed_id:
        message.reply_text("You cannot join two federations from one chat")
        return

    if len(args) >= 1:
        getfed = sql.search_fed_by_id(args[0])
        if not getfed:
            message.reply_text("Please enter a valid federation ID")
            return

        x = sql.chat_join_fed(args[0], chat.title, chat.id)
        if not x:
            message.reply_text("Failed to join federation!")
            return

        get_fedlog = sql.get_fed_log(args[0])
        if get_fedlog and ast.literal_eval(get_fedlog):
            context.bot.send_message(
                get_fedlog,
                "Chat *{}* has joined the federation *{}*".format(
                    chat.title, getfed["fname"]
                ),
                parse_mode="markdown",
            )

        message.reply_text(
            "This chat has joined the federation: {}!".format(getfed["fname"])
        )


@typing_action
def leave_fed(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)
    fed_info = sql.get_fed_info(fed_id)

    # administrators = chat.get_administrators().status
    getuser = context.bot.get_chat_member(chat.id, user.id).status
    if getuser in "creator" or user.id in DEV_USERS:
        if sql.chat_leave_fed(chat.id):
            get_fedlog = sql.get_fed_log(fed_id)
            if get_fedlog and ast.literal_eval(get_fedlog):
                context.bot.send_message(
                    get_fedlog,
                    "Chat *{}* has left the federation *{}*".format(
                        chat.title, fed_info["fname"]
                    ),
                    parse_mode="markdown",
                )
            send_message(
                update.effective_message,
                "This chat has left the federation {}!".format(fed_info["fname"]),
            )
        else:
            update.effective_message.reply_text(
                "How can you leave a federation that you never joined?!"
            )
    else:
        update.effective_message.reply_text("Only group creators can use this command!")


@typing_action
def user_join_fed(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)

    if is_user_fed_owner(fed_id, user.id) or user.id in DEV_USERS:
        user_id = extract_user(msg, args)
        if user_id:
            user = context.bot.get_chat(user_id)
        elif not msg.reply_to_message and not args:
            user = msg.from_user
        elif not msg.reply_to_message and (
            not args
            or (
                len(args) >= 1
                and not args[0].startswith("@")
                and not args[0].isdigit()
                and not msg.parse_entities([MessageEntity.TEXT_MENTION])
            )
        ):
            msg.reply_text("I cannot extract user from this message")
            return
        else:
            LOGGER.warning("error")
        getuser = sql.search_user_in_fed(fed_id, user_id)
        fed_id = sql.get_fed_id(chat.id)
        info = sql.get_fed_info(fed_id)
        get_owner = ast.literal_eval(info["fusers"])["owner"]
        get_owner = context.bot.get_chat(get_owner).id
        if user_id == get_owner:
            update.effective_message.reply_text(
                "You do know that the user is the federation owner, right? RIGHT?"
            )
            return
        if getuser:
            update.effective_message.reply_text(
                "I cannot promote users who are already federation admins! But, I can remove them if you want!"
            )
            return
        if user_id == context.bot.id:
            update.effective_message.reply_text(
                "I already am a federation admin in all federations!"
            )
            return
        res = sql.user_join_fed(fed_id, user_id)
        if res:
            update.effective_message.reply_text("Successfully Promoted!")
        else:
            update.effective_message.reply_text("Failed to promote!")
    else:
        update.effective_message.reply_text("Only federation owners can do this!")


@typing_action
def user_demote_fed(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)

    if is_user_fed_owner(fed_id, user.id):
        msg = update.effective_message
        user_id = extract_user(msg, args)
        if user_id:
            user = context.bot.get_chat(user_id)

        elif not msg.reply_to_message and not args:
            user = msg.from_user

        elif not msg.reply_to_message and (
            not args
            or (
                len(args) >= 1
                and not args[0].startswith("@")
                and not args[0].isdigit()
                and not msg.parse_entities([MessageEntity.TEXT_MENTION])
            )
        ):
            msg.reply_text("I cannot extract user from this message")
            return
        else:
            LOGGER.warning("error")

        if user_id == context.bot.id:
            update.effective_message.reply_text(
                "The thing you are trying to demote me from will fail to work without me! Just saying."
            )
            return

        if not sql.search_user_in_fed(fed_id, user_id):
            update.effective_message.reply_text(
                "I cannot demote people who are not federation admins!"
            )
            return

        res = sql.user_demote_fed(fed_id, user_id)
        if res:
            update.effective_message.reply_text("Get out of here!")
        else:
            update.effective_message.reply_text("Demotion failed!")
    else:
        update.effective_message.reply_text("Only federation owners can do this!")
        return


@typing_action
def fed_info(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    args = context.args
    if args:
        fed_id = args[0]
    else:
        fed_id = sql.get_fed_id(chat.id)
        if not fed_id:
            send_message(
                update.effective_message, "This group is not in any federation!"
            )
            return
    info = sql.get_fed_info(fed_id)
    if not is_user_fed_admin(fed_id, user.id):
        update.effective_message.reply_text("Only a federation admin can do this!")
        return

    owner = context.bot.get_chat(info["owner"])
    try:
        owner_name = owner.first_name + " " + owner.last_name
    except BaseException:
        owner_name = owner.first_name
    FEDADMIN = sql.all_fed_users(fed_id)
    FEDADMIN.append(int(owner.id))
    TotalAdminFed = len(FEDADMIN)

    user = update.effective_user
    chat = update.effective_chat
    info = sql.get_fed_info(fed_id)

    text = "<b>ℹ️ Federation Information:</b>"
    text += "\nFedID: <code>{}</code>".format(fed_id)
    text += "\nName: {}".format(info["fname"])
    text += "\nCreator: {}".format(mention_html(owner.id, owner_name))
    text += "\nAll Admins: <code>{}</code>".format(TotalAdminFed)
    getfban = sql.get_all_fban_users(fed_id)
    text += "\nTotal banned users: <code>{}</code>".format(len(getfban))
    getfchat = sql.all_fed_chats(fed_id)
    text += "\nNumber of groups in this federation: <code>{}</code>".format(
        len(getfchat)
    )

    update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


@typing_action
def fed_admin(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text("This group is not in any federation!")
        return

    if not is_user_fed_admin(fed_id, user.id):
        update.effective_message.reply_text("Only federation admins can do this!")
        return

    user = update.effective_user
    chat = update.effective_chat
    info = sql.get_fed_info(fed_id)

    text = "<b>Federation Admin {}:</b>\n\n".format(info["fname"])
    text += "👑 Owner:\n"
    owner = context.bot.get_chat(info["owner"])
    try:
        owner_name = owner.first_name + " " + owner.last_name
    except BaseException:
        owner_name = owner.first_name
    text += " • {}\n".format(mention_html(owner.id, owner_name))

    members = sql.all_fed_members(fed_id)
    if len(members) == 0:
        text += "\n🔱 There is no admin in this federation"
    else:
        text += "\n🔱 Admin:\n"
        for x in members:
            user = context.bot.get_chat(x)
            text += " • {}\n".format(mention_html(user.id, user.first_name))

    update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


@typing_action
def fed_ban(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text(
            "This group is not a part of any federation!"
        )
        return

    info = sql.get_fed_info(fed_id)
    getfednotif = sql.user_feds_report(info["owner"])

    if not is_user_fed_admin(fed_id, user.id):
        update.effective_message.reply_text("Only federation admins can do this!")
        return

    message = update.effective_message

    user_id, reason = extract_unt_fedban(message, args)

    fban, fbanreason, fbantime = sql.get_fban_user(fed_id, user_id)

    if not user_id:
        message.reply_text("You don't seem to be referring to a user")
        return

    if user_id == context.bot.id:
        message.reply_text(
            "What is funnier than kicking the group creator? Self sacrifice."
        )
        return

    if is_user_fed_owner(fed_id, user_id):
        message.reply_text("Why did you try the federation fban?")
        return

    if is_user_fed_admin(fed_id, user_id):
        message.reply_text("He is a federation admin, I can't fban him.")
        return

    if user_id == OWNER_ID:
        message.reply_text("That's a very STUPID idea!")
        return

    if int(user_id) in DEV_USERS:
        message.reply_text("I will not use sudo fban!")
        return

    if int(user_id) in WHITELIST_USERS:
        message.reply_text("This person can't be fbanned!")
        return

    try:
        user_chat = context.bot.get_chat(user_id)
        isvalid = True
        fban_user_id = user_chat.id
        fban_user_name = user_chat.first_name
        fban_user_lname = user_chat.last_name
        fban_user_uname = user_chat.username
    except BadRequest as excp:
        if not str(user_id).isdigit():
            send_message(update.effective_message, excp.message)
            return
        if len(str(user_id)) != 9:
            send_message(update.effective_message, "That's so not a user!")
            return
        isvalid = False
        fban_user_id = int(user_id)
        fban_user_name = "user({})".format(user_id)
        fban_user_lname = None
        fban_user_uname = None

    if isvalid and user_chat.type != "private":
        send_message(update.effective_message, "That's so not a user!")
        return

    if isvalid:
        user_target = mention_html(fban_user_id, fban_user_name)
    else:
        user_target = fban_user_name

    if fban:
        fed_name = info["fname"]
        if reason == "":
            reason = "No reason given."

        temp = sql.un_fban_user(fed_id, fban_user_id)
        if not temp:
            message.reply_text("Failed to update the reason for fedban!")
            return
        x = sql.fban_user(
            fed_id,
            fban_user_id,
            fban_user_name,
            fban_user_lname,
            fban_user_uname,
            reason,
            int(time.time()),
        )
        if not x:
            message.reply_text("Failed to ban from the federation!")
            return

        fed_chats = sql.all_fed_chats(fed_id)
        # Will send to current chat
        context.bot.send_message(
            chat.id,
            "<b>New FederationBan</b>"
            "\n<b>Federation:</b> {}"
            "\n<b>Federation Admin:</b> {}"
            "\n<b>User:</b> {}"
            "\n<b>User ID:</b> <code>{}</code>"
            "\n<b>Reason:</b> {}".format(
                fed_name,
                mention_html(user.id, user.first_name),
                user_target,
                fban_user_id,
                reason,
            ),
            parse_mode="HTML",
        )
        # Send message to owner if fednotif is enabled
        if getfednotif:
            context.bot.send_message(
                info["owner"],
                "<b>FedBan reason updated</b>"
                "\n<b>Federation:</b> {}"
                "\n<b>Federation Admin:</b> {}"
                "\n<b>User:</b> {}"
                "\n<b>User ID:</b> <code>{}</code>"
                "\n<b>Reason:</b> {}".format(
                    fed_name,
                    mention_html(user.id, user.first_name),
                    user_target,
                    fban_user_id,
                    reason,
                ),
                parse_mode="HTML",
            )
        # If fedlog is set, then send message, except fedlog is current chat
        get_fedlog = sql.get_fed_log(fed_id)
        if get_fedlog and int(get_fedlog) != int(chat.id):
            context.bot.send_message(
                get_fedlog,
                "<b>FedBan reason updated</b>"
                "\n<b>Federation:</b> {}"
                "\n<b>Federation Admin:</b> {}"
                "\n<b>User:</b> {}"
                "\n<b>User ID:</b> <code>{}</code>"
                "\n<b>Reason:</b> {}".format(
                    fed_name,
                    mention_html(user.id, user.first_name),
                    user_target,
                    fban_user_id,
                    reason,
                ),
                parse_mode="HTML",
            )
        for fedschat in fed_chats:
            try:
                # Do not spam all fed chats
                """
				context.bot.send_message(chat, "<b>FedBan reason updated</b>" \
							 "\n<b>Federation:</b> {}" \
							 "\n<b>Federation Admin:</b> {}" \
							 "\n<b>User:</b> {}" \
							 "\n<b>User ID:</b> <code>{}</code>" \
							 "\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason), parse_mode="HTML")
				"""
                context.bot.kick_chat_member(fedschat, fban_user_id)
            except BadRequest as excp:
                if excp.message in FBAN_ERRORS:
                    try:
                        dispatcher.bot.getChat(fedschat)
                    except Unauthorized:
                        sql.chat_leave_fed(fedschat)
                        LOGGER.info(
                            "Chat {} has leave fed {} because I was kicked".format(
                                fedschat, info["fname"]
                            )
                        )
                        continue
                elif excp.message == "User_id_invalid":
                    break
                else:
                    LOGGER.warning(
                        "Could not fban on {} because: {}".format(chat, excp.message)
                    )
            except TelegramError:
                pass
        # Also do not spam all fed admins

        # send_to_list(bot, FEDADMIN,
        # "<b>FedBan reason updated</b>" \
        # "\n<b>Federation:</b> {}" \
        # "\n<b>Federation Admin:</b> {}" \
        # "\n<b>User:</b> {}" \
        # "\n<b>User ID:</b> <code>{}</code>" \
        # "\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason),
        # html=True)

        # Fban for fed subscriber
        subscriber = list(sql.get_subscriber(fed_id))
        if len(subscriber) != 0:
            for fedsid in subscriber:
                all_fedschat = sql.all_fed_chats(fedsid)
                for fedschat in all_fedschat:
                    try:
                        context.bot.kick_chat_member(fedschat, fban_user_id)
                    except BadRequest as excp:
                        if excp.message in FBAN_ERRORS:
                            try:
                                dispatcher.bot.getChat(fedschat)
                            except Unauthorized:
                                targetfed_id = sql.get_fed_id(fedschat)
                                sql.unsubs_fed(fed_id, targetfed_id)
                                LOGGER.info(
                                    "Chat {} has unsub fed {} because I was kicked".format(
                                        fedschat, info["fname"]
                                    )
                                )
                                continue
                        elif excp.message == "User_id_invalid":
                            break
                        else:
                            LOGGER.warning(
                                "Unable to fban on {} because: {}".format(
                                    fedschat, excp.message
                                )
                            )
                    except TelegramError:
                        pass
        # send_message(update.effective_message, "Fedban Reason has been updated.")
        return

    fed_name = info["fname"]

    starting = "Starting a federation ban for {} in the Federation <b>{}</b>.".format(
        user_target, fed_name
    )
    update.effective_message.reply_text(starting, parse_mode=ParseMode.HTML)

    if reason == "":
        reason = "No reason given."

    x = sql.fban_user(
        fed_id,
        fban_user_id,
        fban_user_name,
        fban_user_lname,
        fban_user_uname,
        reason,
        int(time.time()),
    )
    if not x:
        message.reply_text("Failed to ban from the federation!")
        return

    fed_chats = sql.all_fed_chats(fed_id)
    # Will send to current chat
    context.bot.send_message(
        chat.id,
        "<b>FedBan reason updated</b>"
        "\n<b>Federation:</b> {}"
        "\n<b>Federation Admin:</b> {}"
        "\n<b>User:</b> {}"
        "\n<b>User ID:</b> <code>{}</code>"
        "\n<b>Reason:</b> {}".format(
            fed_name,
            mention_html(user.id, user.first_name),
            user_target,
            fban_user_id,
            reason,
        ),
        parse_mode="HTML",
    )
    # Send message to owner if fednotif is enabled
    if getfednotif:
        context.bot.send_message(
            info["owner"],
            "<b>FedBan reason updated</b>"
            "\n<b>Federation:</b> {}"
            "\n<b>Federation Admin:</b> {}"
            "\n<b>User:</b> {}"
            "\n<b>User ID:</b> <code>{}</code>"
            "\n<b>Reason:</b> {}".format(
                fed_name,
                mention_html(user.id, user.first_name),
                user_target,
                fban_user_id,
                reason,
            ),
            parse_mode="HTML",
        )
    # If fedlog is set, then send message, except fedlog is current chat
    get_fedlog = sql.get_fed_log(fed_id)
    if get_fedlog and int(get_fedlog) != int(chat.id):
        context.bot.send_message(
            get_fedlog,
            "<b>FedBan reason updated</b>"
            "\n<b>Federation:</b> {}"
            "\n<b>Federation Admin:</b> {}"
            "\n<b>User:</b> {}"
            "\n<b>User ID:</b> <code>{}</code>"
            "\n<b>Reason:</b> {}".format(
                fed_name,
                mention_html(user.id, user.first_name),
                user_target,
                fban_user_id,
                reason,
            ),
            parse_mode="HTML",
        )
    chats_in_fed = 0
    for fedschat in fed_chats:
        chats_in_fed += 1
        try:
            # Do not spamming all fed chats
            """
			context.bot.send_message(chat, "<b>FedBan reason updated</b>" \
							"\n<b>Federation:</b> {}" \
							"\n<b>Federation Admin:</b> {}" \
							"\n<b>User:</b> {}" \
							"\n<b>User ID:</b> <code>{}</code>" \
							"\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason), parse_mode="HTML")
			"""
            context.bot.kick_chat_member(fedschat, fban_user_id)
        except BadRequest as excp:
            if excp.message in FBAN_ERRORS:
                pass
            elif excp.message == "User_id_invalid":
                break
            else:
                LOGGER.warning(
                    "Could not fban on {} because: {}".format(chat, excp.message)
                )
        except TelegramError:
            pass

        # Also do not spamming all fed admins
        """
		send_to_list(bot, FEDADMIN,
				 "<b>FedBan reason updated</b>" \
							 "\n<b>Federation:</b> {}" \
							 "\n<b>Federation Admin:</b> {}" \
							 "\n<b>User:</b> {}" \
							 "\n<b>User ID:</b> <code>{}</code>" \
							 "\n<b>Reason:</b> {}".format(fed_name, mention_html(user.id, user.first_name), user_target, fban_user_id, reason), 
							html=True)
		"""

        # Fban for fed subscriber
        subscriber = list(sql.get_subscriber(fed_id))
        if len(subscriber) != 0:
            for fedsid in subscriber:
                all_fedschat = sql.all_fed_chats(fedsid)
                for fedschat in all_fedschat:
                    try:
                        context.bot.kick_chat_member(fedschat, fban_user_id)
                    except BadRequest as excp:
                        if excp.message in FBAN_ERRORS:
                            try:
                                dispatcher.bot.getChat(fedschat)
                            except Unauthorized:
                                targetfed_id = sql.get_fed_id(fedschat)
                                sql.unsubs_fed(fed_id, targetfed_id)
                                LOGGER.info(
                                    "Chat {} has unsub fed {} because I was kicked".format(
                                        fedschat, info["fname"]
                                    )
                                )
                                continue
                        elif excp.message == "User_id_invalid":
                            break
                        else:
                            LOGGER.warning(
                                "Unable to fban on {} because: {}".format(
                                    fedschat, excp.message
                                )
                            )
                    except TelegramError:
                        pass
    if chats_in_fed == 0:
        send_message(update.effective_message, "Fedban affected 0 chats. ")
    elif chats_in_fed > 0:
        send_message(
            update.effective_message, "Fedban affected {} chats. ".format(chats_in_fed)
        )


@typing_action
def unfban(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text(
            "This group is not a part of any federation!"
        )
        return

    info = sql.get_fed_info(fed_id)
    getfednotif = sql.user_feds_report(info["owner"])

    if not is_user_fed_admin(fed_id, user.id):
        update.effective_message.reply_text("Only federation admins can do this!")
        return

    user_id = extract_user_fban(message, args)
    if not user_id:
        message.reply_text("You do not seem to be referring to a user.")
        return

    try:
        user_chat = context.bot.get_chat(user_id)
        isvalid = True
        fban_user_id = user_chat.id
        fban_user_name = user_chat.first_name
        fban_user_lname = user_chat.last_name
        fban_user_uname = user_chat.username
    except BadRequest as excp:
        if not str(user_id).isdigit():
            send_message(update.effective_message, excp.message)
            return
        if len(str(user_id)) != 9:
            send_message(update.effective_message, "That's so not a user!")
            return
        isvalid = False
        fban_user_id = int(user_id)
        fban_user_name = "user({})".format(user_id)
        fban_user_lname = None
        fban_user_uname = None

    if isvalid and user_chat.type != "private":
        message.reply_text("That's so not a user!")
        return

    if isvalid:
        user_target = mention_html(fban_user_id, fban_user_name)
    else:
        user_target = fban_user_name

    fban, fbanreason, fbantime = sql.get_fban_user(fed_id, fban_user_id)
    if not fban:
        message.reply_text("This user is not fbanned!")
        return

    message.reply_text(
        "I'll give {} another chance in this federation".format(user_chat.first_name)
    )

    chat_list = sql.all_fed_chats(fed_id)
    # Will send to current chat
    context.bot.send_message(
        chat.id,
        "<b>Un-FedBan</b>"
        "\n<b>Federation:</b> {}"
        "\n<b>Federation Admin:</b> {}"
        "\n<b>User:</b> {}"
        "\n<b>User ID:</b> <code>{}</code>".format(
            info["fname"],
            mention_html(user.id, user.first_name),
            user_target,
            fban_user_id,
        ),
        parse_mode="HTML",
    )
    # Send message to owner if fednotif is enabled
    if getfednotif:
        context.bot.send_message(
            info["owner"],
            "<b>Un-FedBan</b>"
            "\n<b>Federation:</b> {}"
            "\n<b>Federation Admin:</b> {}"
            "\n<b>User:</b> {}"
            "\n<b>User ID:</b> <code>{}</code>".format(
                info["fname"],
                mention_html(user.id, user.first_name),
                user_target,
                fban_user_id,
            ),
            parse_mode="HTML",
        )
    # If fedlog is set, then send message, except fedlog is current chat
    get_fedlog = sql.get_fed_log(fed_id)
    if get_fedlog and int(get_fedlog) != int(chat.id):
        context.bot.send_message(
            get_fedlog,
            "<b>Un-FedBan</b>"
            "\n<b>Federation:</b> {}"
            "\n<b>Federation Admin:</b> {}"
            "\n<b>User:</b> {}"
            "\n<b>User ID:</b> <code>{}</code>".format(
                info["fname"],
                mention_html(user.id, user.first_name),
                user_target,
                fban_user_id,
            ),
            parse_mode="HTML",
        )
    unfbanned_in_chats = 0
    for fedchats in chat_list:
        unfbanned_in_chats += 1
        try:
            member = context.bot.get_chat_member(fedchats, user_id)
            if member.status == "kicked":
                context.bot.unban_chat_member(fedchats, user_id)
            # Do not spamming all fed chats
            """
			context.bot.send_message(chat, "<b>Un-FedBan</b>" \
						 "\n<b>Federation:</b> {}" \
						 "\n<b>Federation Admin:</b> {}" \
						 "\n<b>User:</b> {}" \
						 "\n<b>User ID:</b> <code>{}</code>".format(info['fname'], mention_html(user.id, user.first_name), user_target, fban_user_id), parse_mode="HTML")
			"""
        except BadRequest as excp:
            if excp.message in UNFBAN_ERRORS:
                pass
            elif excp.message == "User_id_invalid":
                break
            else:
                LOGGER.warning(
                    "Could not fban on {} because: {}".format(chat, excp.message)
                )
        except TelegramError:
            pass

    try:
        x = sql.un_fban_user(fed_id, user_id)
        if not x:
            send_message(
                update.effective_message,
                "Un-fban failed, this user may already be un-fedbanned!",
            )
            return
    except Exception:
        pass

    # UnFban for fed subscriber
    subscriber = list(sql.get_subscriber(fed_id))
    if len(subscriber) != 0:
        for fedsid in subscriber:
            all_fedschat = sql.all_fed_chats(fedsid)
            for fedschat in all_fedschat:
                try:
                    context.bot.unban_chat_member(fedchats, user_id)
                except BadRequest as excp:
                    if excp.message in FBAN_ERRORS:
                        try:
                            dispatcher.bot.getChat(fedschat)
                        except Unauthorized:
                            targetfed_id = sql.get_fed_id(fedschat)
                            sql.unsubs_fed(fed_id, targetfed_id)
                            LOGGER.info(
                                "Chat {} has unsub fed {} because I was kicked".format(
                                    fedschat, info["fname"]
                                )
                            )
                            continue
                    elif excp.message == "User_id_invalid":
                        break
                    else:
                        LOGGER.warning(
                            "Unable to fban on {} because: {}".format(
                                fedschat, excp.message
                            )
                        )
                except TelegramError:
                    pass

    if unfbanned_in_chats == 0:
        send_message(
            update.effective_message, "This person has been un-fbanned in 0 chats."
        )
    if unfbanned_in_chats > 0:
        send_message(
            update.effective_message,
            "This person has been un-fbanned in {} chats.".format(unfbanned_in_chats),
        )
    # Also do not spamming all fed admins
    """
	FEDADMIN = sql.all_fed_users(fed_id)
	for x in FEDADMIN:
		getreport = sql.user_feds_report(x)
		if getreport == False:
			FEDADMIN.remove(x)
	send_to_list(bot, FEDADMIN,
			 "<b>Un-FedBan</b>" \
			 "\n<b>Federation:</b> {}" \
			 "\n<b>Federation Admin:</b> {}" \
			 "\n<b>User:</b> {}" \
			 "\n<b>User ID:</b> <code>{}</code>".format(info['fname'], mention_html(user.id, user.first_name),
												 mention_html(user_chat.id, user_chat.first_name),
															  user_chat.id),
			html=True)
	"""


@typing_action
def set_frules(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text("This chat is not in any federation!")
        return

    if not is_user_fed_admin(fed_id, user.id):
        update.effective_message.reply_text("Only fed admins can do this!")
        return

    if len(args) >= 1:
        msg = update.effective_message
        raw_text = msg.text
        args = raw_text.split(None, 1)  # use python's maxsplit to separate cmd and args
        if len(args) == 2:
            txt = args[1]
            offset = len(txt) - len(raw_text)  # set correct offset relative to command
            markdown_rules = markdown_parser(
                txt, entities=msg.parse_entities(), offset=offset
            )
        x = sql.set_frules(fed_id, markdown_rules)
        if not x:
            update.effective_message.reply_text(
                "Big F! There is an error while setting federation rules!"
            )
            return

        rules = sql.get_fed_info(fed_id)["frules"]
        getfed = sql.get_fed_info(fed_id)
        get_fedlog = sql.get_fed_log(fed_id)
        if get_fedlog and ast.literal_eval(get_fedlog):
            context.bot.send_message(
                get_fedlog,
                "*{}* has changed federation rules for fed *{}*".format(
                    user.first_name, getfed["fname"]
                ),
                parse_mode="markdown",
            )
        update.effective_message.reply_text(f"Rules have been changed to :\n{rules}!")
    else:
        update.effective_message.reply_text("Please write rules to set it up!")


@typing_action
def get_frules(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)
    if not fed_id:
        update.effective_message.reply_text("This chat is not in any federation!")
        return

    rules = sql.get_frules(fed_id)
    text = "*Rules in this fed:*\n"
    text += rules
    update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@typing_action
def fed_broadcast(update: Update, context: CallbackContext):
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    if args:
        chat = update.effective_chat  # type: Optional[Chat]
        fed_id = sql.get_fed_id(chat.id)
        fedinfo = sql.get_fed_info(fed_id)
        # Parsing md
        raw_text = msg.text
        args = raw_text.split(None, 1)  # use python's maxsplit to separate cmd and args
        txt = args[1]
        offset = len(txt) - len(raw_text)  # set correct offset relative to command
        text_parser = markdown_parser(txt, entities=msg.parse_entities(), offset=offset)
        text = text_parser
        try:
            broadcaster = user.first_name
        except BaseException:
            broadcaster = user.first_name + " " + user.last_name
        text += "\n\n- {}".format(mention_markdown(user.id, broadcaster))
        chat_list = sql.all_fed_chats(fed_id)
        failed = 0
        for chat in chat_list:
            title = "*New broadcast from Fed {}*\n".format(fedinfo["fname"])
            try:
                context.bot.sendMessage(chat, title + text, parse_mode="markdown")
            except TelegramError:
                try:
                    dispatcher.bot.getChat(chat)
                except Unauthorized:
                    failed += 1
                    sql.chat_leave_fed(chat)
                    LOGGER.info(
                        "Chat {} has leave fed {} because I was kicked".format(
                            chat, fedinfo["fname"]
                        )
                    )
                    continue
                failed += 1
                LOGGER.warning("Couldn't send broadcast to {}".format(str(chat)))

        send_text = "The federation broadcast is complete"
        if failed >= 1:
            send_text += "{} the group failed to receive the message, probably because it left the Federation.".format(
                failed
            )
        update.effective_message.reply_text(send_text)


@send_action(ChatAction.UPLOAD_DOCUMENT)
def fed_ban_list(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    args = context.args
    chat_data = context.chat_data

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)
    info = sql.get_fed_info(fed_id)

    if not fed_id:
        update.effective_message.reply_text(
            "This group is not a part of any federation!"
        )
        return

    if not is_user_fed_owner(fed_id, user.id):
        update.effective_message.reply_text("Only Federation owners can do this!")
        return

    user = update.effective_user  # type: Optional[Chat]
    chat = update.effective_chat  # type: Optional[Chat]
    getfban = sql.get_all_fban_users(fed_id)
    if len(getfban) == 0:
        update.effective_message.reply_text(
            "The federation ban list of {} is empty".format(info["fname"]),
            parse_mode=ParseMode.HTML,
        )
        return

    if args:
        if args[0] == "json":
            jam = time.time()
            new_jam = jam + 1800
            cek = get_chat(chat.id, chat_data)
            if cek.get("status") and jam <= int(cek.get("value")):
                waktu = time.strftime(
                    "%H:%M:%S %d/%m/%Y", time.localtime(cek.get("value"))
                )
                update.effective_message.reply_text(
                    "You can backup your data once every 30 minutes!\nYou can back up data again at `{}`".format(
                        waktu
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            if user.id not in DEV_USERS:
                put_chat(chat.id, new_jam, chat_data)
            backups = ""
            for users in getfban:
                getuserinfo = sql.get_all_fban_users_target(fed_id, users)
                json_parser = {
                    "user_id": users,
                    "first_name": getuserinfo["first_name"],
                    "last_name": getuserinfo["last_name"],
                    "user_name": getuserinfo["user_name"],
                    "reason": getuserinfo["reason"],
                }
                backups += json.dumps(json_parser)
                backups += "\n"
            with BytesIO(str.encode(backups)) as output:
                output.name = "zeldris_fbanned_users.json"
                update.effective_message.reply_document(
                    document=output,
                    filename="zeldris_fbanned_users.json",
                    caption="Total {} User are blocked by the Federation {}.".format(
                        len(getfban), info["fname"]
                    ),
                )
            return
        if args[0] == "csv":
            jam = time.time()
            new_jam = jam + 1800
            cek = get_chat(chat.id, chat_data)
            if cek.get("status") and jam <= int(cek.get("value")):
                waktu = time.strftime(
                    "%H:%M:%S %d/%m/%Y", time.localtime(cek.get("value"))
                )
                update.effective_message.reply_text(
                    "You can back up data once every 30 minutes!\nYou can back up data again at `{}`".format(
                        waktu
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            if user.id not in DEV_USERS:
                put_chat(chat.id, new_jam, chat_data)
            backups = "id,firstname,lastname,username,reason\n"
            for users in getfban:
                getuserinfo = sql.get_all_fban_users_target(fed_id, users)
                backups += (
                    "{user_id},{first_name},{last_name},{user_name},{reason}".format(
                        user_id=users,
                        first_name=getuserinfo["first_name"],
                        last_name=getuserinfo["last_name"],
                        user_name=getuserinfo["user_name"],
                        reason=getuserinfo["reason"],
                    )
                )
                backups += "\n"
            with BytesIO(str.encode(backups)) as output:
                output.name = "zeldris_fbanned_users.csv"
                update.effective_message.reply_document(
                    document=output,
                    filename="zeldris_fbanned_users.csv",
                    caption="Total {} User are blocked by Federation {}.".format(
                        len(getfban), info["fname"]
                    ),
                )
            return

    text = "<b>{} users have been banned from the federation {}:</b>\n".format(
        len(getfban), info["fname"]
    )
    for users in getfban:
        getuserinfo = sql.get_all_fban_users_target(fed_id, users)
        if not getuserinfo:
            text = "There are no users banned from the federation {}".format(
                info["fname"]
            )
            break
        user_name = getuserinfo["first_name"]
        if getuserinfo["last_name"]:
            user_name += " " + getuserinfo["last_name"]
        text += " • {} (<code>{}</code>)\n".format(
            mention_html(users, user_name), users
        )

    try:
        update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
    except BaseException:
        jam = time.time()
        new_jam = jam + 1800
        cek = get_chat(chat.id, chat_data)
        if cek.get("status") and jam <= int(cek.get("value")):
            waktu = time.strftime("%H:%M:%S %d/%m/%Y", time.localtime(cek.get("value")))
            update.effective_message.reply_text(
                "You can back up data once every 30 minutes!\nYou can back up data again at `{}`".format(
                    waktu
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        if user.id not in DEV_USERS:
            put_chat(chat.id, new_jam, chat_data)
        cleanr = re.compile("<.*?>")
        cleantext = re.sub(cleanr, "", text)
        with BytesIO(str.encode(cleantext)) as output:
            output.name = "fbanlist.txt"
            update.effective_message.reply_document(
                document=output,
                filename="fbanlist.txt",
                caption="The following is a list of users who are currently fbanned in the Federation {}.".format(
                    info["fname"]
                ),
            )


@typing_action
def fed_notif(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_messag
    args = context.args
    fed_id = sql.get_fed_id(chat.id)

    if not fed_id:
        update.effective_message.reply_text(
            "This group is not a part of any federation!"
        )
        return

    if args:
        if args[0] in ("yes", "on"):
            sql.set_feds_setting(user.id, True)
            msg.reply_text(
                "Reporting Federation back up! Every user who is fban / unfban you will be notified via PM."
            )
        elif args[0] in ("no", "off"):
            sql.set_feds_setting(user.id, False)
            msg.reply_text(
                "Reporting Federation has stopped! Every user who is fban / unfban you will not be notified via PM."
            )
        else:
            msg.reply_text("Please enter `on`/`off`", parse_mode="markdown")
    else:
        getreport = sql.user_feds_report(user.id)
        msg.reply_text(
            "Your current Federation report preferences: `{}`".format(getreport),
            parse_mode="markdown",
        )


@typing_action
def fed_chats(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)
    info = sql.get_fed_info(fed_id)

    if not fed_id:
        update.effective_message.reply_text(
            "This group is not a part of any federation!"
        )
        return

    if not is_user_fed_admin(fed_id, user.id):
        update.effective_message.reply_text("Only federation admins can do this!")
        return

    getlist = sql.all_fed_chats(fed_id)
    if len(getlist) == 0:
        update.effective_message.reply_text(
            "No users are fbanned from the federation {}".format(info["fname"]),
            parse_mode=ParseMode.HTML,
        )
        return

    text = "<b>New chat joined the federation {}:</b>\n".format(info["fname"])
    for chats in getlist:
        try:
            chat_name = dispatcher.bot.getChat(chats).title
        except Unauthorized:
            sql.chat_leave_fed(chats)
            LOGGER.info(
                "Chat {} has leave fed {} because I was kicked".format(
                    chats, info["fname"]
                )
            )
            continue
        text += " • {} (<code>{}</code>)\n".format(chat_name, chats)

    try:
        update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
    except BaseException:
        cleanr = re.compile("<.*?>")
        cleantext = re.sub(cleanr, "", text)
        with BytesIO(str.encode(cleantext)) as output:
            output.name = "fedchats.txt"
            update.effective_message.reply_document(
                document=output,
                filename="fedchats.txt",
                caption="Here is a list of all the chats that joined the federation {}.".format(
                    info["fname"]
                ),
            )


@typing_action
def fed_import_bans(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    chat_data = context.chat_data

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)
    # info = sql.get_fed_info(fed_id)
    getfed = sql.get_fed_info(fed_id)

    if not fed_id:
        update.effective_message.reply_text(
            "This group is not a part of any federation!"
        )
        return

    if not is_user_fed_owner(fed_id, user.id):
        update.effective_message.reply_text("Only Federation owners can do this!")
        return

    if msg.reply_to_message and msg.reply_to_message.document:
        jam = time.time()
        new_jam = jam + 1800
        cek = get_chat(chat.id, chat_data)
        if cek.get("status") and jam <= int(cek.get("value")):
            waktu = time.strftime("%H:%M:%S %d/%m/%Y", time.localtime(cek.get("value")))
            update.effective_message.reply_text(
                "You can get your data once every 30 minutes!\nYou can get data again at `{}`".format(
                    waktu
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        if user.id not in DEV_USERS:
            put_chat(chat.id, new_jam, chat_data)
        # if int(int(msg.reply_to_message.document.file_size)/1024) >= 200:
        # 	msg.reply_text("This file is too big!")
        # 	return
        success = 0
        failed = 0
        try:
            file_info = context.bot.get_file(msg.reply_to_message.document.file_id)
        except BadRequest:
            msg.reply_text(
                "Try downloading and re-uploading the file, this one seems broken!"
            )
            return
        fileformat = msg.reply_to_message.document.file_name.split(".")[-1]
        if fileformat == "json":
            multi_fed_id = []
            multi_import_userid = []
            multi_import_firstname = []
            multi_import_lastname = []
            multi_import_username = []
            multi_import_reason = []
            with BytesIO() as file:
                file_info.download(out=file)
                file.seek(0)
                reading = file.read().decode("UTF-8")
                splitting = reading.split("\n")
                for x in splitting:
                    if x == "":
                        continue
                    try:
                        data = json.loads(x)
                    except json.decoder.JSONDecodeError:
                        failed += 1
                        continue
                    try:
                        import_userid = int(data["user_id"])  # Make sure it int
                        import_firstname = str(data["first_name"])
                        import_lastname = str(data["last_name"])
                        import_username = str(data["user_name"])
                        import_reason = str(data["reason"])
                    except ValueError:
                        failed += 1
                        continue
                    # Checking user
                    if int(import_userid) == context.bot.id:
                        failed += 1
                        continue
                    if is_user_fed_owner(fed_id, import_userid):
                        failed += 1
                        continue
                    if is_user_fed_admin(fed_id, import_userid):
                        failed += 1
                        continue
                    if str(import_userid) == str(OWNER_ID):
                        failed += 1
                        continue
                    if int(import_userid) in DEV_USERS:
                        failed += 1
                        continue
                    if int(import_userid) in WHITELIST_USERS:
                        failed += 1
                        continue
                    multi_fed_id.append(fed_id)
                    multi_import_userid.append(str(import_userid))
                    multi_import_firstname.append(import_firstname)
                    multi_import_lastname.append(import_lastname)
                    multi_import_username.append(import_username)
                    multi_import_reason.append(import_reason)
                    success += 1
                sql.multi_fban_user(
                    multi_fed_id,
                    multi_import_userid,
                    multi_import_firstname,
                    multi_import_lastname,
                    multi_import_username,
                    multi_import_reason,
                )
            text = "Blocks were successfully imported. {} people are blocked.".format(
                success
            )
            if failed >= 1:
                text += " {} Failed to import.".format(failed)
            get_fedlog = sql.get_fed_log(fed_id)
            if get_fedlog and ast.literal_eval(get_fedlog):
                teks = "Fed *{}* has successfully imported data. {} banned.".format(
                    getfed["fname"], success
                )
                if failed >= 1:
                    teks += " {} Failed to import.".format(failed)
                context.bot.send_message(get_fedlog, teks, parse_mode="markdown")
        elif fileformat == "csv":
            multi_fed_id = []
            multi_import_userid = []
            multi_import_firstname = []
            multi_import_lastname = []
            multi_import_username = []
            multi_import_reason = []
            file_info.download(
                "fban_{}.csv".format(msg.reply_to_message.document.file_id)
            )
            with open(
                "fban_{}.csv".format(msg.reply_to_message.document.file_id),
                "r",
                encoding="utf8",
            ) as csvFile:
                reader = csv.reader(csvFile)
                for data in reader:
                    try:
                        import_userid = int(data[0])  # Make sure it int
                        import_firstname = str(data[1])
                        import_lastname = str(data[2])
                        import_username = str(data[3])
                        import_reason = str(data[4])
                    except ValueError:
                        failed += 1
                        continue
                    # Checking user
                    if int(import_userid) == context.bot.id:
                        failed += 1
                        continue
                    if is_user_fed_owner(fed_id, import_userid):
                        failed += 1
                        continue
                    if is_user_fed_admin(fed_id, import_userid):
                        failed += 1
                        continue
                    if str(import_userid) == str(OWNER_ID):
                        failed += 1
                        continue
                    if int(import_userid) in DEV_USERS:
                        failed += 1
                        continue
                    if int(import_userid) in WHITELIST_USERS:
                        failed += 1
                        continue
                    multi_fed_id.append(fed_id)
                    multi_import_userid.append(str(import_userid))
                    multi_import_firstname.append(import_firstname)
                    multi_import_lastname.append(import_lastname)
                    multi_import_username.append(import_username)
                    multi_import_reason.append(import_reason)
                    success += 1
                    # t = ThreadWithReturnValue(target=sql.fban_user, args=(fed_id, str(import_userid),
                    # import_firstname, import_lastname, import_username, import_reason,)) t.start()
                sql.multi_fban_user(
                    multi_fed_id,
                    multi_import_userid,
                    multi_import_firstname,
                    multi_import_lastname,
                    multi_import_username,
                    multi_import_reason,
                )
            csvFile.close()
            os.remove("fban_{}.csv".format(msg.reply_to_message.document.file_id))
            text = "Files were imported successfully. {} people banned.".format(success)
            if failed >= 1:
                text += " {} Failed to import.".format(failed)
            get_fedlog = sql.get_fed_log(fed_id)
            if get_fedlog and ast.literal_eval(get_fedlog):
                teks = "Fed *{}* has successfully imported data. {} banned.".format(
                    getfed["fname"], success
                )
                if failed >= 1:
                    teks += " {} Failed to import.".format(failed)
                context.bot.send_message(get_fedlog, teks, parse_mode="markdown")
        else:
            send_message(update.effective_message, "This file is not supported.")
            return
        send_message(update.effective_message, text)


def del_fed_button(update, _):
    query = update.callback_query
    fed_id = query.data.split("_")[1]

    if fed_id == "cancel":
        query.message.edit_text("Federation deletion cancelled")
        return

    getfed = sql.get_fed_info(fed_id)
    if getfed:
        delete = sql.del_fed(fed_id)
        if delete:
            query.message.edit_text(
                "You have removed your Federation! Now all the Groups that are connected with `{}` do not have a "
                "Federation.".format(getfed["fname"]),
                parse_mode="markdown",
            )


@typing_action
def fed_stat_user(update: Update, context: CallbackContext):
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    if args and args[0].isdigit():
        user_id = args[0]
    else:
        user_id = extract_user(msg, args)
    if user_id:
        if len(args) == 2 and args[0].isdigit():
            fed_id = args[1]
            user_name, reason, fbantime = sql.get_user_fban(fed_id, str(user_id))
            if fbantime:
                fbantime = time.strftime("%d/%m/%Y", time.localtime(fbantime))
            else:
                fbantime = "Unavaiable"
            if not user_name:
                send_message(
                    update.effective_message,
                    "Fed {} not found!".format(fed_id),
                    parse_mode="markdown",
                )
                return
            if user_name == "" or user_name is None:
                user_name = "He/she"
            if not reason:
                send_message(
                    update.effective_message,
                    "{} is not banned in this federation!".format(user_name),
                )
            else:
                teks = "{} banned in this federation because:\n`{}`\n*Banned at:* `{}`".format(
                    user_name, reason, fbantime
                )
                send_message(update.effective_message, teks, parse_mode="markdown")
            return
        user_name, fbanlist = sql.get_user_fbanlist(str(user_id))
        if user_name == "":
            try:
                user_name = context.bot.get_chat(user_id).first_name
            except BadRequest:
                user_name = "He/she"
            if user_name == "" or user_name is None:
                user_name = "He/she"
        if len(fbanlist) == 0:
            send_message(
                update.effective_message,
                "{} is not banned in any federation!".format(user_name),
            )
            return
        teks = "{} has been banned in this federation:\n".format(user_name)
        for x in fbanlist:
            teks += "- `{}`: {}\n".format(x[0], x[1][:20])
        teks += "\nIf you want to find out more about the reasons for Fedban specifically, use /fbanstat <FedID>"
        send_message(update.effective_message, teks, parse_mode="markdown")

    elif not msg.reply_to_message and not args:
        user_id = msg.from_user.id
        user_name, fbanlist = sql.get_user_fbanlist(user_id)
        if user_name == "":
            user_name = msg.from_user.first_name
        if len(fbanlist) == 0:
            send_message(
                update.effective_message,
                "{} is not banned in any federation!".format(user_name),
            )
        else:
            teks = "{} has been banned in this federation:\n".format(user_name)
            for x in fbanlist:
                teks += "- `{}`: {}\n".format(x[0], x[1][:20])
            teks += "\nIf you want to find out more about the reasons for Fedban specifically, use /fbanstat <FedID>"
            send_message(update.effective_message, teks, parse_mode="markdown")

    else:
        fed_id = args[0]
        fedinfo = sql.get_fed_info(fed_id)
        if not fedinfo:
            send_message(update.effective_message, "Fed {} not found!".format(fed_id))
            return
        name, reason, fbantime = sql.get_user_fban(fed_id, msg.from_user.id)
        if fbantime:
            fbantime = time.strftime("%d/%m/%Y", time.localtime(fbantime))
        else:
            fbantime = "Unavaiable"
        if not name:
            name = msg.from_user.first_name
        if not reason:
            send_message(
                update.effective_message,
                "{} is not banned in this federation".format(name),
            )
            return
        send_message(
            update.effective_message,
            "{} banned in this federation because:\n`{}`\n*Banned at:* `{}`".format(
                name, reason, fbantime
            ),
            parse_mode="markdown",
        )


@typing_action
def set_fed_log(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    if args:
        fedinfo = sql.get_fed_info(args[0])
        if not fedinfo:
            send_message(update.effective_message, "This Federation does not exist!")
            return
        isowner = is_user_fed_owner(args[0], user.id)
        if not isowner:
            send_message(
                update.effective_message,
                "Only federation creator can set federation logs.",
            )
            return
        setlog = sql.set_fed_log(args[0], chat.id)
        if setlog:
            send_message(
                update.effective_message,
                "Federation log `{}` has been set to {}".format(
                    fedinfo["fname"], chat.title
                ),
                parse_mode="markdown",
            )
    else:
        send_message(
            update.effective_message, "You have not provided your federated ID!"
        )


@typing_action
def unset_fed_log(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    if args:
        fedinfo = sql.get_fed_info(args[0])
        if not fedinfo:
            send_message(update.effective_message, "This Federation does not exist!")
            return
        isowner = is_user_fed_owner(args[0], user.id)
        if not isowner:
            send_message(
                update.effective_message,
                "Only federation creator can set federation logs.",
            )
            return
        setlog = sql.set_fed_log(args[0], None)
        if setlog:
            send_message(
                update.effective_message,
                "Federation log `{}` has been revoked on {}".format(
                    fedinfo["fname"], chat.title
                ),
                parse_mode="markdown",
            )
    else:
        send_message(
            update.effective_message, "You have not provided your federated ID!"
        )


@typing_action
def subs_feds(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)
    fedinfo = sql.get_fed_info(fed_id)

    if not fed_id:
        send_message(update.effective_message, "This chat is not in any federation!")
        return

    if not is_user_fed_owner(fed_id, user.id):
        send_message(update.effective_message, "Only fed owner can do this!")
        return

    if args:
        getfed = sql.search_fed_by_id(args[0])
        if not getfed:
            send_message(
                update.effective_message, "Please enter a valid federation id."
            )
            return
        subfed = sql.subs_fed(args[0], fed_id)
        if subfed:
            send_message(
                update.effective_message,
                "Federation `{}` has subscribe the federation `{}`. Every time there is a Fedban from that "
                "federation, this federation will also banned that user.".format(
                    fedinfo["fname"], getfed["fname"]
                ),
                parse_mode="markdown",
            )
            get_fedlog = sql.get_fed_log(args[0])
            if get_fedlog and int(get_fedlog) != int(chat.id):
                context.bot.send_message(
                    get_fedlog,
                    "Federation `{}` has subscribe the federation `{}`".format(
                        fedinfo["fname"], getfed["fname"]
                    ),
                    parse_mode="markdown",
                )
        else:
            send_message(
                update.effective_message,
                "Federation `{}` already subscribe the federation `{}`.".format(
                    fedinfo["fname"], getfed["fname"]
                ),
                parse_mode="markdown",
            )
    else:
        send_message(
            update.effective_message, "You have not provided your federated ID!"
        )


@typing_action
def unsubs_feds(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)
    fedinfo = sql.get_fed_info(fed_id)

    if not fed_id:
        send_message(update.effective_message, "This chat is not in any federation!")
        return

    if not is_user_fed_owner(fed_id, user.id):
        send_message(update.effective_message, "Only fed owner can do this!")
        return

    if args:
        getfed = sql.search_fed_by_id(args[0])
        if not getfed:
            send_message(
                update.effective_message, "Please enter a valid federation id."
            )
            return
        subfed = sql.unsubs_fed(args[0], fed_id)
        if subfed:
            send_message(
                update.effective_message,
                "Federation `{}` now unsubscribe fed `{}`.".format(
                    fedinfo["fname"], getfed["fname"]
                ),
                parse_mode="markdown",
            )
            get_fedlog = sql.get_fed_log(args[0])
            if get_fedlog and int(get_fedlog) != int(chat.id):
                context.bot.send_message(
                    get_fedlog,
                    "Federation `{}` has unsubscribe fed `{}`.".format(
                        fedinfo["fname"], getfed["fname"]
                    ),
                    parse_mode="markdown",
                )
        else:
            send_message(
                update.effective_message,
                "Federation `{}` is not subscribing `{}`.".format(
                    fedinfo["fname"], getfed["fname"]
                ),
                parse_mode="markdown",
            )
    else:
        send_message(
            update.effective_message, "You have not provided your federated ID!"
        )


@typing_action
def get_myfedsubs(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    if chat.type == "private":
        send_message(
            update.effective_message,
            "This command is specific to the group, not to the PM! ",
        )
        return

    fed_id = sql.get_fed_id(chat.id)
    fedinfo = sql.get_fed_info(fed_id)

    if not fed_id:
        send_message(update.effective_message, "This chat is not in any federation!")
        return

    if not is_user_fed_owner(fed_id, user.id):
        send_message(update.effective_message, "Only fed owner can do this!")
        return

    getmy = sql.get_mysubs(fed_id)

    if getmy is None:
        send_message(
            update.effective_message,
            "Federation `{}` is not subscribing any federation.".format(
                fedinfo["fname"]
            ),
            parse_mode="markdown",
        )
        return
    listfed = "Federation `{}` is subscribing federation:\n".format(fedinfo["fname"])
    for x in getmy:
        listfed += "- `{}`\n".format(x)
    listfed += (
        "\nTo get fed info `/fedinfo <fedid>`. To unsubscribe `/unsubfed <fedid>`."
    )
    send_message(update.effective_message, listfed, parse_mode="markdown")


@typing_action
def get_myfeds_list(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    args = context.args

    fedowner = sql.get_user_owner_fed_full(user.id)
    if fedowner:
        text = "*You are owner of feds:\n*"
        for f in fedowner:
            text += "- `{}`: *{}*\n".format(f["fed_id"], f["fed"]["fname"])
    else:
        text = "*You are not have any feds!*"
    send_message(update.effective_message, text, parse_mode="markdown")


def is_user_fed_admin(fed_id, user_id):
    fed_admins = sql.all_fed_users(fed_id)
    if not fed_admins:
        return False
    if int(user_id) in fed_admins or int(user_id) == OWNER_ID:
        return True
    return False


def is_user_fed_owner(fed_id, user_id):
    getsql = sql.get_fed_info(fed_id)
    if not getsql:
        return False
    getfedowner = ast.literal_eval(getsql["fusers"])
    if getfedowner is None or getfedowner is False:
        return False
    getfedowner = getfedowner["owner"]
    return str(user_id) == getfedowner or int(user_id) == OWNER_ID


def welcome_fed(update: Update, context: CallbackContext):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    fed_id = sql.get_fed_id(chat.id)
    fban, fbanreason, fbantime = sql.get_fban_user(fed_id, user.id)
    if fban:
        update.effective_message.reply_text(
            "This user is banned in current federation! I will remove him."
        )
        context.bot.kick_chat_member(chat.id, user.id)
        return True
    return False


def __stats__():
    all_fbanned = sql.get_all_fban_users_global()
    all_feds = sql.get_all_feds_users_global()
    return "× {} users banned, in {} federations".format(
        len(all_fbanned), len(all_feds)
    )


def __user_info__(user_id, chat_id):
    fed_id = sql.get_fed_id(chat_id)
    if fed_id:
        fban, fbanreason, fbantime = sql.get_fban_user(fed_id, user_id)
        info = sql.get_fed_info(fed_id)
        infoname = info["fname"]

        if int(info["owner"]) == user_id:
            text = (
                "This user is the owner of the current Federation: <b>{}</b>.".format(
                    infoname
                )
            )
        elif is_user_fed_admin(fed_id, user_id):
            text = (
                "This user is the admin of the current Federation: <b>{}</b>.".format(
                    infoname
                )
            )

        elif fban:
            text = "<b>Banned in current Fed</b>: Yes"
            text += "\n<b>Reason</b>: {}".format(fbanreason)
        else:
            text = "<b>Banned in current Fed</b>: No"
    else:
        text = ""
    return text


# Temporary data
def put_chat(chat_id, value, chat_data):
    # print(chat_data)
    status = bool(value)
    chat_data[chat_id] = {"federation": {"status": status, "value": value}}


def get_chat(chat_id, chat_data):
    # print(chat_data)
    try:
        return chat_data[chat_id]["federation"]
    except KeyError:
        return {"status": False, "value": False}


__mod_name__ = "Federations"

__help__ = """
Ah, group management. Everything is fun, until the spammer starts entering your group, and you have to 
block it. Then you need to start banning more, and more, and it hurts. But then you have many groups, and you don't 
want this spammer to be in one of your groups - how can you deal? Do you have to manually block it, in all your groups? 

No longer! With Federation, you can make a ban in one chat overlap with all other chats.
You can even designate admin federations, so your trusted admin can ban all the chats you want to protect.

*Commands Available*:

× /newfed <fedname>: Create a new Federation with the name given. Users are only allowed to have one Federation. This method can also be used to rename the Federation. (max. 64 characters)
× /delfed: Delete your Federation, and any information related to it. Will not cancel blocked users.
× /fedinfo <FedID>: Information about the specified Federation.
× /joinfed <FedID>: Join the current chat to the Federation. Only chat owners can do this. Every chat can only be in one Federation.
× /leavefed <FedID>: Leave the Federation given. Only chat owners can do this.
× /fpromote <user>: Promote Users to give fed admin. Fed owner only.
× /fdemote <user>: Drops the User from the admin Federation to a normal User. Fed owner only.
× /fban <user>: Prohibits users from all federations where this chat takes place, and executors have control over.
× /unfban <user>: Cancel User from all federations where this chat takes place, and that the executor has control over.
× /setfrules: Arrange Federation rules.
× /frules: See Federation regulations.
× /chatfed: See the Federation in the current chat.
× /fedadmins: Show Federation admin.
× /fbanlist: Displays all users who are victimized at the Federation at this time.
× /fednotif <on / off>: Federation settings not in PM when there are users who are fban / unfban.
× /fedchats: Get all the chats that are connected in the Federation.
× /importfbans: Reply to the Federation backup message file to import the banned list to the Federation now.
"""

NEW_FED_HANDLER = CommandHandler("newfed", new_fed, run_async=True)
DEL_FED_HANDLER = CommandHandler("delfed", del_fed, pass_args=True, run_async=True)
JOIN_FED_HANDLER = CommandHandler("joinfed", join_fed, pass_args=True, run_async=True)
LEAVE_FED_HANDLER = CommandHandler(
    "leavefed", leave_fed, pass_args=True, run_async=True
)
PROMOTE_FED_HANDLER = CommandHandler(
    "fpromote", user_join_fed, pass_args=True, run_async=True
)
DEMOTE_FED_HANDLER = CommandHandler(
    "fdemote", user_demote_fed, pass_args=True, run_async=True
)
INFO_FED_HANDLER = CommandHandler("fedinfo", fed_info, pass_args=True, run_async=True)
BAN_FED_HANDLER = DisableAbleCommandHandler(
    ["fban", "fedban"],
    fed_ban,
    pass_args=True,
    run_async=True,
)
UN_BAN_FED_HANDLER = CommandHandler("unfban", unfban, pass_args=True, run_async=True)
FED_BROADCAST_HANDLER = CommandHandler(
    "fbroadcast", fed_broadcast, pass_args=True, run_async=True
)
FED_SET_RULES_HANDLER = CommandHandler(
    "setfrules", set_frules, pass_args=True, run_async=True
)
FED_GET_RULES_HANDLER = CommandHandler(
    "frules", get_frules, pass_args=True, run_async=True
)
FED_CHAT_HANDLER = CommandHandler("chatfed", fed_chat, pass_args=True, run_async=True)
FED_ADMIN_HANDLER = CommandHandler(
    "fedadmins", fed_admin, pass_args=True, run_async=True
)
FED_USERBAN_HANDLER = CommandHandler(
    "fbanlist",
    fed_ban_list,
    pass_args=True,
    pass_chat_data=True,
    run_async=True,
)
FED_NOTIF_HANDLER = CommandHandler(
    "fednotif", fed_notif, pass_args=True, run_async=True
)
FED_CHATLIST_HANDLER = CommandHandler(
    "fedchats", fed_chats, pass_args=True, run_async=True
)
FED_IMPORTBAN_HANDLER = CommandHandler(
    "importfbans", fed_import_bans, pass_chat_data=True, run_async=True
)
FEDSTAT_USER = DisableAbleCommandHandler(
    ["fedstat", "fbanstat"],
    fed_stat_user,
    pass_args=True,
    run_async=True,
)
SET_FED_LOG = CommandHandler("setfedlog", set_fed_log, pass_args=True, run_async=True)
UNSET_FED_LOG = CommandHandler(
    "unsetfedlog", unset_fed_log, pass_args=True, run_async=True
)
SUBS_FED = CommandHandler("subfed", subs_feds, pass_args=True, run_async=True)
UNSUBS_FED = CommandHandler("unsubfed", unsubs_feds, pass_args=True, run_async=True)
MY_SUB_FED = CommandHandler("fedsubs", get_myfedsubs, pass_args=True, run_async=True)
MY_FEDS_LIST = CommandHandler("myfeds", get_myfeds_list, run_async=True)
DELETEBTN_FED_HANDLER = CallbackQueryHandler(
    del_fed_button, pattern=r"rmfed_", run_async=True
)

dispatcher.add_handler(NEW_FED_HANDLER)
dispatcher.add_handler(DEL_FED_HANDLER)
dispatcher.add_handler(JOIN_FED_HANDLER)
dispatcher.add_handler(LEAVE_FED_HANDLER)
dispatcher.add_handler(PROMOTE_FED_HANDLER)
dispatcher.add_handler(DEMOTE_FED_HANDLER)
dispatcher.add_handler(INFO_FED_HANDLER)
dispatcher.add_handler(BAN_FED_HANDLER)
dispatcher.add_handler(UN_BAN_FED_HANDLER)
dispatcher.add_handler(FED_BROADCAST_HANDLER)
dispatcher.add_handler(FED_SET_RULES_HANDLER)
dispatcher.add_handler(FED_GET_RULES_HANDLER)
dispatcher.add_handler(FED_CHAT_HANDLER)
dispatcher.add_handler(FED_ADMIN_HANDLER)
dispatcher.add_handler(FED_USERBAN_HANDLER)
dispatcher.add_handler(FED_NOTIF_HANDLER)
dispatcher.add_handler(FED_CHATLIST_HANDLER)
dispatcher.add_handler(FED_IMPORTBAN_HANDLER)
dispatcher.add_handler(FEDSTAT_USER)
dispatcher.add_handler(SET_FED_LOG)
dispatcher.add_handler(UNSET_FED_LOG)
dispatcher.add_handler(SUBS_FED)
dispatcher.add_handler(UNSUBS_FED)
dispatcher.add_handler(MY_SUB_FED)
dispatcher.add_handler(MY_FEDS_LIST)

dispatcher.add_handler(DELETEBTN_FED_HANDLER)

dispatcher.add_handler(MY_FEDS_LIST)

dispatcher.add_handler(DELETEBTN_FED_HANDLER)
