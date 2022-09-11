from functools import wraps
import os

from dotenv import load_dotenv
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import piecash
from piecash import Book, Account, Transaction, Split


load_dotenv()


class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    USER_ID = int(os.getenv("USER_ID", 0))
    
    DATABASE_URI = os.getenv("DATABASE_URI")
    READONLY = bool(int(os.getenv("READONLY", 1)))

    PER_PAGE = int(os.getenv("PER_PAGE", 3))
    
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
            book = piecash.open_book(uri_conn=config.DATABASE_URI, readonly=readonly,
                                     open_if_lock=readonly, do_backup=False)
            ret = func(*args, book, **kwargs)
            book.close()
            return ret
        return wrapper
    return decorator


def add_children_markup(mk: InlineKeyboardMarkup, account: Account, callback_prefix: str = "show"):
    for acc in account.children:
        mk.add(InlineKeyboardButton(f"{acc.name:<20} {acc.get_balance():15,.2f} {acc.commodity.mnemonic}",
                                    callback_data=f"{callback_prefix}_{acc.guid}"))
    if account.type != "ROOT":
        if account.parent.type == "ROOT":
            mk.add(InlineKeyboardButton("<<<", callback_data=f"{callback_prefix}_root"))
        else:
            mk.add(InlineKeyboardButton("<<<", callback_data=f"{callback_prefix}_{account.parent.guid}"))
        mk.add(InlineKeyboardButton("^ Начало ^", callback_data=f"{callback_prefix}_root"))

    return mk


@bot.message_handler(commands=["start", "accounts"])
@open_book()
@protected
def command_accounts(message: Message, book):
    mk = InlineKeyboardMarkup()
    mk = add_children_markup(mk, book.root_account)
    bot.send_message(message.chat.id, "Основные счета:", reply_markup=mk)


@bot.callback_query_handler(func=lambda call: call.data.startswith("show"))
@open_book()
@protected
def callback_show(call: CallbackQuery, book: Book):
    guid = call.data.split("_")[1]
    if guid == "root":
        acc = book.root_account
        text = "<b>Основные счета</b>"
    else:
        acc = book.accounts(guid=guid)
        text = f"<b>{acc.name}</b>\n{acc.get_balance():,.2f}"

    mk = InlineKeyboardMarkup()
    if not acc.placeholder and acc.type != "ROOT":
        mk.add(
            InlineKeyboardButton("Журнал", callback_data=f"journal_{acc.guid}_0"),
            InlineKeyboardButton("Проводка", callback_data=f"transfer_new_{acc.guid}")
        )
    mk = add_children_markup(mk, acc)
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.id,
        text=text,
        reply_markup=mk,
        parse_mode="html"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("journal"))
@open_book()
@protected
def callback_journal(call: CallbackQuery, book: Book):
    _, guid, page = call.data.split("_")
    page = int(page)

    acc: Account = book.accounts(guid=guid)
    journal = book.query(Split).join(Transaction)\
        .filter(Split.account == acc)\
        .order_by(Transaction.post_date.desc())
    j_count = journal.count()
    journal = journal.limit(config.PER_PAGE).offset(page * config.PER_PAGE)

    text = f"<b>{acc.name}</b>\n{acc.get_balance():,.2f}\n<pre>"
    for record in journal:
        text += f"{record.transaction.post_date} | {record.transaction.description} | {record.value * acc.sign}\n"
        for sp in record.transaction.splits:
            text += f"{sp.account.fullname} {sp.value}\n"
        text += "\n"
    text += "</pre>"

    mk = InlineKeyboardMarkup()
    if page != j_count - 1:
        mk.add(InlineKeyboardButton(">>>", callback_data=f"journal_{acc.guid}_{page + 1}"))
    if page != 0:
        mk.add(InlineKeyboardButton("<<<", callback_data=f"journal_{acc.guid}_{page - 1}"))
    mk.add(InlineKeyboardButton("К счетам", callback_data=f"show_{acc.guid}"))
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.id,
        text=text,
        reply_markup=mk,
        parse_mode="html"
    )


temp_transfer_storage = {}


@bot.callback_query_handler(func=lambda call: call.data.startswith("transfer"))
@open_book()
@protected
def callback_transfer(call: CallbackQuery, book: Book):
    _, action, *guid = call.data.split("_")
    if action == "new":
        temp_transfer_storage[(call.message.chat.id, call.message.id)] = guid[0]
        mk = InlineKeyboardMarkup()
        mk = add_children_markup(mk, book.root_account, "transfer_ch")
        mk.add(InlineKeyboardButton("! Отмена !", callback_data="transfer_cancel"))
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text="Выберите второй счёт",
            reply_markup=mk
        )
    elif action == "ch":
        if guid[0] == "root":
            acc: Account = book.root_account
        else:
            acc: Account = book.accounts(guid=guid[0])

        mk = InlineKeyboardMarkup()
        if not acc.placeholder and acc.type != "ROOT":
            mk.add(InlineKeyboardButton(">> Выбрать <<", callback_data=f"transfer_ok_{acc.guid}"),)
        mk = add_children_markup(mk, acc, "transfer_ch")
        mk.add(InlineKeyboardButton("! Отмена !", callback_data="transfer_cancel"))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=f"Выберите второй счёт\n<b>{acc.name}</b>\n{acc.get_balance():,.2f}",
            reply_markup=mk,
            parse_mode="html"
        )
    elif action == "ok":
        acc: Account = book.accounts(guid=guid[0])
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text="Введите описание",
            reply_markup=InlineKeyboardMarkup()
        )
        bot.register_next_step_handler(call.message, step_description_transfer,
                                       first=temp_transfer_storage.pop((call.message.chat.id, call.message.id)),
                                       second=acc.guid)
    elif action == "cancel":
        first = temp_transfer_storage.pop((call.message.chat.id, call.message.id))
        call.data = f"show_{first}"
        callback_show(call)


@protected
def step_description_transfer(message: Message, first, second):
    description = message.text
    bot.send_message(message.chat.id, "Введите сумму")
    bot.register_next_step_handler(message, step_amount_transfer,
                                   first=first, second=second, description=description)


@open_book(False)
@protected
def step_amount_transfer(message: Message, book: Book, first, second, description):
    amount = int(message.text)
    first = book.accounts(guid=first)
    second = book.accounts(guid=second)
    tr = Transaction(currency=book.default_currency, description=description,
                     splits=[
                         Split(account=first, value=-amount),
                         Split(account=second, value=amount)
                     ])
    book.flush()
    book.save()
    bot.send_message(message.chat.id, "Проводка успешно добавлена!")
    command_accounts(message)


if __name__ == "__main__":
    bot.polling()
