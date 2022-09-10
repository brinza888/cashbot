from functools import wraps
import os

from dotenv import load_dotenv
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import piecash


load_dotenv()


class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    USER_ID = int(os.getenv("USER_ID", 0))
    
    DATABASE_URI = os.getenv("DATABASE_URI")
    READONLY = bool(int(os.getenv("READONLY", "1")))
    
    def __init__(self):
        if not self.DATABASE_URI:
            raise ValueError("DATABASE_URI required")
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN requried")


config = Config()
bot = TeleBot(config.BOT_TOKEN)


def protected(func):
    @wraps(func)
    def wrapper(message: Message, *args, **kwargs):
        if config.USER_ID and message.from_user.id != config.USER_ID:
            return
        return func(message, *args, **kwargs)
    return wrapper


def open_book(readonly=True):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            book = piecash.open_book(uri_conn=config.DATABASE_URI, readonly=readonly)
            ret = func(*args, book, **kwargs)
            book.close()
            return ret
        return wrapper
    return decorator


def get_account_markup(account):
    mk = InlineKeyboardMarkup()
    if not account.placeholder and account.type != "ROOT":
        mk.add(
            InlineKeyboardButton("Журнал", callback_data=f"journal_{account.guid}"),
            InlineKeyboardButton("Проводка", callback_data=f"transfer_{account.guid}")
        )
    for acc in account.children:
        mk.add(InlineKeyboardButton(f"{acc.name:<20} {acc.get_balance():15,.2f} {acc.commodity.mnemonic}",
                                    callback_data=f"acc_{acc.guid}"))
    if account.type != "ROOT":
        if account.parent.type == "ROOT":
            mk.add(InlineKeyboardButton("<<<", callback_data="acc_root"))
        else:
            mk.add(InlineKeyboardButton("<<<", callback_data=f"acc_{account.parent.guid}"))
    return mk


@bot.message_handler(commands=["accounts"])
@open_book()
@protected
def command_accounts(message: Message, book):
    bot.send_message(message.chat.id, "Основные счета:", reply_markup=get_account_markup(book.root_account))


@bot.callback_query_handler(func=lambda call: call.data.startswith("acc"))
@open_book()
@protected
def callback_acc(call: CallbackQuery, book):
    guid = call.data.split("_")[1]
    if guid == "root":
        acc = book.root_account
        text = "Основные счета".center(50, "-")
    else:
        acc = book.accounts(guid=guid)
        text = (f"{acc.name:-^50}\n"
                f"Баланс: {acc.get_balance():,.2f}")

    mk = get_account_markup(acc)
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.id,
        text=text,
        reply_markup=mk
    )


if __name__ == "__main__":
    bot.polling()
