from functools import wraps
import os

from dotenv import load_dotenv
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import piecash
from piecash import Book, Account, Transaction, Split

from i18n import I18N


load_dotenv()


class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    USER_ID = int(os.getenv("USER_ID", 0))
    
    DATABASE_URI = os.getenv("DATABASE_URI")
    READONLY = bool(int(os.getenv("READONLY", 1)))

    LANG_CODE = os.getenv("LANG_CODE", "en")
    LANG_FILE = os.getenv("LANG_FILE", "i18n.yaml")

    PER_PAGE = int(os.getenv("PER_PAGE", 3))
    
    def __init__(self):
        if not self.DATABASE_URI:
            raise ValueError("DATABASE_URI required")
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN required")


config = Config()
bot = TeleBot(config.BOT_TOKEN)
i18n = I18N(lang_code=config.LANG_CODE, file=config.LANG_FILE)


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


def get_net_assets(book: Book):
    assets = 0
    liab = 0
    for acc in book.root_account.children:
        if acc.type == "ASSET":
            assets += acc.get_balance()
        elif acc.type == "LIABILITY":
            liab += acc.get_balance()
    return assets - liab


def get_income(book: Book):
    income = 0
    for acc in book.root_account.children:
        if acc.type == "INCOME":
            income += acc.get_balance()
    return income


def get_expense(book: Book):
    expense = 0
    for acc in book.root_account.children:
        if acc.type == "EXPENSE":
            expense += acc.get_balance()
    return expense


def get_financial_results(book: Book):
    income, expense = get_income(book), get_expense(book)
    profit = income - expense
    return income, expense, profit


def get_root_text(book: Book):
    income, expense, profit = get_financial_results(book)
    return (f"<pre>"
            f"{i18n.t('net_assets'):>15}: {get_net_assets(book):>15,.2f}\n"
            f"{i18n.t('income'):>15}: {income:>15,.2f}\n"
            f"{i18n.t('expense'):>15}: {expense:>15,.2f}\n"
            f"{i18n.t('profit'):>15}: {profit:>15,.2f}</pre>\n\n"
            f"<u><b>{i18n.t('main')}</b></u>")


def add_children_markup(mk: InlineKeyboardMarkup, account: Account, callback_prefix: str = "show"):
    for acc in account.children:
        mk.add(InlineKeyboardButton(f"{acc.name:<20} {acc.get_balance():15,.2f} {acc.commodity.mnemonic}",
                                    callback_data=f"{callback_prefix}_{acc.guid}"))
    if account.type != "ROOT":
        if account.parent.type == "ROOT":
            mk.add(InlineKeyboardButton("<<<", callback_data=f"{callback_prefix}_root"))
        else:
            mk.add(InlineKeyboardButton("<<<", callback_data=f"{callback_prefix}_{account.parent.guid}"))
        mk.add(InlineKeyboardButton(f"{i18n.t('to_main')}", callback_data=f"{callback_prefix}_root"))

    return mk


@bot.message_handler(commands=["start", "accounts"])
@open_book()
@protected
def command_accounts(message: Message, book):
    mk = InlineKeyboardMarkup()
    mk = add_children_markup(mk, book.root_account)
    bot.send_message(message.chat.id, get_root_text(book), reply_markup=mk, parse_mode="html")


@bot.callback_query_handler(func=lambda call: call.data.startswith("show"))
@open_book()
@protected
def callback_show(call: CallbackQuery, book: Book):
    guid = call.data.split("_")[1]
    if guid == "root":
        acc = book.root_account
        text = get_root_text(book)
    else:
        acc = book.accounts(guid=guid)
        text = f"<b>{acc.name}</b>\n{acc.get_balance():,.2f} {acc.commodity.mnemonic}"

    mk = InlineKeyboardMarkup()
    if not acc.placeholder and acc.type != "ROOT":
        mk.add(
            InlineKeyboardButton(f"{i18n.t('journal')}", callback_data=f"journal_{acc.guid}_0"),
            InlineKeyboardButton(f"{i18n.t('new_transaction')}", callback_data=f"transfer_new_{acc.guid}")
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
    mk.add(InlineKeyboardButton(f"{i18n.t('to_accounts')}", callback_data=f"show_{acc.guid}"))
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
        mk.add(InlineKeyboardButton(f"{i18n.t('cancel')}", callback_data="transfer_cancel"))
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=i18n.t('second_account'),
            reply_markup=mk
        )
    elif action == "ch":
        if guid[0] == "root":
            acc: Account = book.root_account
        else:
            acc: Account = book.accounts(guid=guid[0])

        mk = InlineKeyboardMarkup()
        if not acc.placeholder and acc.type != "ROOT":
            mk.add(InlineKeyboardButton(f"{i18n.t('choose')}", callback_data=f"transfer_ok_{acc.guid}"),)
        mk = add_children_markup(mk, acc, "transfer_ch")
        mk.add(InlineKeyboardButton(f"{i18n.t('cancel')}", callback_data="transfer_cancel"))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=f"{i18n.t('second_account')}\n<b>{acc.name}</b>\n{acc.get_balance():,.2f}",
            reply_markup=mk,
            parse_mode="html"
        )
    elif action == "ok":
        acc: Account = book.accounts(guid=guid[0])
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            text=i18n.t("type_description"),
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
    bot.send_message(message.chat.id, i18n.t("type_amount"))
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
    bot.send_message(message.chat.id, i18n.t("transaction_added"))
    command_accounts(message)


if __name__ == "__main__":
    bot.polling()
