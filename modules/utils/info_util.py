"""Common info needed in both command and callback handlers"""
from random import choice
from telegram import Bot, Update, Message, CallbackQuery, ReplyMarkup, Chat
from telegram.ext import CallbackContext
from telegram.error import BadRequest
from modules.debug.log_manager import logger
from modules.data import config_map, read_md, PendingPost, PublishedPost, User
from modules.utils.keyboard_util import get_approve_kb, get_vote_kb


class EventInfo():
    """Class that contains all the relevant information related to an event
    """

    def __init__(self,
                 bot: Bot,
                 ctx: CallbackContext,
                 update: Update = None,
                 message: Message = None,
                 query: CallbackQuery = None):
        self.__bot = bot
        self.__ctx = ctx
        self.__update = update
        self.__message = message
        self.__query = query

    @property
    def bot(self) -> Bot:
        """:class:`telegram.Bot`: Istance of the telegram bot"""
        return self.__bot

    @property
    def context(self) -> CallbackContext:
        """:class:`telegram.ext.CallbackContext`: Context generated by some event"""
        return self.__ctx

    @property
    def update(self) -> Update:
        """:class:`telegram.update.Update`: Update generated by some event. Defaults to None"""
        return self.__update

    @property
    def message(self) -> Message:
        """:class:`telegram.Message`: Message that caused the update. Defaults to None"""
        return self.__message

    @property
    def bot_data(self) -> dict:
        """:class:`dict`: Data related to the bot. Is not persistent between restarts"""
        return self.__ctx.bot_data

    @property
    def user_data(self) -> dict:
        """:class:`dict`: Data related to the user. Is not persistent between restarts"""
        return self.__ctx.user_data

    @property
    def chat_id(self) -> int:
        """:class:`int`: Id of the chat where the event happened. Defaults to None"""
        if self.__message is None:
            return None
        return self.__message.chat_id

    @property
    def chat_type(self) -> str:
        """:class:`str`: Type of the chat where the event happened. Defaults to None"""
        if self.__message is None:
            return None
        return self.__message.chat.type

    @property
    def is_private_chat(self) -> bool:
        """:class:`bool`: Whether the chat is private or not
        """
        if self.chat_type is None:
            return None
        return self.chat_type == Chat.PRIVATE

    @property
    def text(self) -> str:
        """:class:`str`: Text of the message that caused the update. Defaults to None"""
        if self.__message is None:
            return None
        return self.__message.text

    @property
    def message_id(self) -> int:
        """:class:`int`: Id of the message that caused the update. Defaults to None"""
        if self.__message is None:
            return None
        return self.__message.message_id

    @property
    def is_valid_message_type(self) -> bool:
        """:class:`bool`: Whether or not the type of the message is supported"""
        if self.__message is None:
            return None
        return self.__message.text or self.__message.photo or self.__message.voice or self.__message.audio\
        or self.__message.video or self.__message.animation or self.__message.sticker or self.__message.poll

    @property
    def reply_markup(self) -> ReplyMarkup:
        """:class:`telegram.ReplyMarkup`: Reply_markup of the message that caused the update. Defaults to None"""
        if self.__message is None:
            return None
        return self.__message.reply_markup

    @property
    def user_id(self) -> int:
        """:class:`int`: Id of the user that caused the update. Defaults to None"""
        if self.__query is not None:
            return self.__query.from_user.id
        if self.__message is not None:
            return self.__message.from_user.id
        return None

    @property
    def user_username(self) -> int:
        """:class:`int`: Username of the user that caused the update. Defaults to None"""
        if self.__query is not None:
            return self.__query.from_user.username
        if self.__message is not None:
            return self.__message.from_user.username
        return None

    @property
    def query_id(self) -> int:
        """:class:`int`: Id of the query that caused the update. Defaults to None"""
        if self.__query is None:
            return None
        return self.__query.id

    @property
    def query_data(self) -> str:
        """:class:`str`: Data associated with the query that caused the update. Defaults to None"""
        if self.__query is None:
            return None
        return self.__query.data

    @classmethod
    def from_message(cls, update: Update, ctx: CallbackContext):
        """Istance of EventInfo created by a message update

        Args:
            update (Update): update event
            context (CallbackContext): context passed by the handler

        Returns:
            EventInfo: istance of the class
        """
        return cls(bot=ctx.bot, ctx=ctx, update=update, message=update.message)

    @classmethod
    def from_callback(cls, update: Update, ctx: CallbackContext):
        """Istance of EventInfo created by a callback update

        Args:
            update (Update): update event
            context (CallbackContext): context passed by the handler

        Returns:
            EventInfo: istance of the class
        """
        return cls(bot=ctx.bot, ctx=ctx, update=update, message=update.callback_query.message, query=update.callback_query)

    @classmethod
    def from_job(cls, ctx: CallbackContext):
        """Istance of EventInfo created by a job update

        Args:
            context (CallbackContext): context passed by the handler

        Returns:
            EventInfo: istance of the class
        """
        return cls(bot=ctx.bot, ctx=ctx)

    def answer_callback_query(self, text: str = None):
        """Calls the answer_callback_query method of the bot class, while also handling the exception

        Args:
            text (str, optional): Text to show to the user. Defaults to None.
        """
        try:
            self.__bot.answer_callback_query(callback_query_id=self.query_id, text=text)
        except BadRequest as e:
            logger.warning("On answer_callback_query: %s", e)

    def send_post_to_admins(self) -> bool:
        """Sends the post to the admin group, so it can be approved

        Returns:
            bool: whether or not the operation was successful
        """
        message = self.__message.reply_to_message
        group_id = config_map['meme']['group_id']
        poll = message.poll  # if the message is a poll, get its reference

        try:
            if poll:  # makes sure the poll is anonym
                g_message_id = self.__bot.send_poll(chat_id=group_id,
                                                    question=poll.question,
                                                    options=[option.text for option in poll.options],
                                                    type=poll.type,
                                                    allows_multiple_answers=poll.allows_multiple_answers,
                                                    correct_option_id=poll.correct_option_id,
                                                    reply_markup=get_approve_kb()).message_id
            else:
                g_message_id = self.__bot.copy_message(chat_id=group_id,
                                                       from_chat_id=message.chat_id,
                                                       message_id=message.message_id,
                                                       reply_markup=get_approve_kb()).message_id
        except (BadRequest) as e:
            logger.error("Sending the post on send_post_to: %s", e)
            return False

        PendingPost.create(user_message=message, group_id=group_id, g_message_id=g_message_id)

        return True

    def send_post_to_channel(self, user_id: int):
        """Sends the post to  the channel, so it can be ejoyed by the users (and voted, if comments are disabled)
        """
        message = self.__message
        channel_id = config_map['meme']['channel_id']

        reply_markup = None
        if not config_map['meme']['comments']:  # ... append the voting Inline Keyboard, if comments are not to be supported
            reply_markup = get_vote_kb()

        c_message_id = self.__bot.copy_message(chat_id=channel_id,
                                               from_chat_id=message.chat_id,
                                               message_id=message.message_id,
                                               reply_markup=reply_markup).message_id

        if not config_map['meme']['comments']:  # if the user can vote directly on the post
            PublishedPost.create(c_message_id=c_message_id, channel_id=channel_id)
            sign = self.get_user_sign(user_id=user_id)
            self.__bot.send_message(chat_id=channel_id, text=f"by: {sign}", reply_to_message_id=message.message_id)
        else:  # ... else, if comments are enabled, save the user_id, so the user can be credited
            self.bot_data[f"{channel_id},{c_message_id}"] = user_id

    def send_post_to_channel_group(self):
        """Sends the post to the group associated to the channel, so that users can vote the post (if comments are enabled)
        """
        message = self.__message
        channel_group_id = config_map['meme']['channel_group_id']
        forward_from_chat_id = message.forward_from_chat.id
        forward_from_id = message.forward_from_message_id
        user_id = self.bot_data[f"{forward_from_chat_id},{forward_from_id}"]
        del self.bot_data[f"{forward_from_chat_id},{forward_from_id}"]

        sign = self.get_user_sign(user_id=user_id)
        post_message_id = self.__bot.send_message(chat_id=channel_group_id,
                                                  text=f"by: {sign}",
                                                  reply_markup=get_vote_kb(),
                                                  reply_to_message_id=message.message_id).message_id

        PublishedPost.create(channel_id=channel_group_id, c_message_id=post_message_id)

    def get_user_sign(self, user_id: int) -> str:
        """Generates a sign for the user. It will be a random name for an anonym user

        Args:
            user_id (int): id of the user that originated the post

        Returns:
            str: the sign of the user
        """
        sign = choice(read_md("anonym_names").split("\n"))  # random sign
        if User(user_id).is_credited:  # the user wants to be credited
            username = self.__bot.getChat(user_id).username
            if username:
                sign = "@" + username

        return sign
