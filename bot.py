"""
KomuNado bot
"""
# -*- coding: UTF-8 -*-

import logging
import os
import base64
import json
import time
from telegram import (
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardMarkup, 
    Update,
)
from telegram.ext import (
    Updater, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    CallbackContext, 
    Filters, 
    BasePersistence,
    utils,
)
from collections import defaultdict
from google.cloud import vision
from google.cloud.vision import ImageAnnotatorClient
from uuid import uuid4
from io import BytesIO


PORT = int(os.environ.get('PORT', 8443))
print("Port: ", PORT)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)
TOKEN = os.environ["TOKEN"]
ADMINCHATID = os.environ["ADMINCHATID"]

# misc text constants
ALLOWED_LANGUAGES = {"RU", "EN"}
NEW = "new"
PRELANG = "prelang"
LANG = "lang"
TOS = "tos"
CONTACT = "contact"
LIMIT = "limit"
DELETED = "deleted"
backhand_index_pointing_down = u'\U0001F447'

# load config
with open('config.json') as f:
    config = json.load(f)

# shortcuts
btn = config["buttons"]
txt = config["messagetext"]
lim = config["limits"]

# Return chat info (lang, status) by context (chat_data)
def get_chat(context):
    try:
        status = context.chat_data["status"]
    except KeyError:
        status = NEW

    try:
        lang = context.chat_data["lang"]
    except KeyError:
        lang = ""

    try:
        active_posts = context.chat_data["active_posts"]
    except KeyError:
        active_posts = 0

    return status, lang, active_posts


#######################################################################################################################
# PERSISTENCE MANAGEMENT CLASS                                                                                        #
#######################################################################################################################
class DummyPersistence(BasePersistence):
    def _init_(self):
        print("Persistence instance created")

    def get_bot_data(self):
        print("get_bot_data, self = ", self)
        bd: utils.types.BD = {}
        return bd

    def update_bot_data(self, bot_data):
        print("update_bot_data, bot_data = ", bot_data, ", self = ", self)

    def refresh_bot_data(self, bot_data):
        print("refresh_bot_data, bot_data = ", bot_data, ", self = ", self)

    def get_chat_data(self):
        print("get_chat_data, self = ", self)
        d: DefaultDict(int, utils.types.UD) = defaultdict(dict)
        return d

    def update_chat_data(self, chat_id, chat_data):
        print("update_chat_data, chat_id = ", chat_id, ", chat_data = ", chat_data)

    def refresh_chat_data(self, chat_id, chat_data):
        print("refresh_chat_data, chat_id = ", chat_id, ", chat_data = ", chat_data)

    def get_user_data(self):
        print("get_user_data, self = ", self)
#        ud: utils.types.UD = {}
        d: DefaultDict(int, utils.types.UD) = defaultdict(dict)
        return d

    def update_user_data(self, user_id, user_data):
        print("update_user_data, user_id = ", user_id, ", user_data = ", user_data)

    def refresh_user_data(self, user_id, user_data):
        print("refresh_user_data, user_id = ", user_id, ", user_data = ", user_data)

    def get_callback_data(self):
        print("get_callback_data")

    def update_callback_data(self, callback_data):
        print("update_callback_data, callback_data = ", callback_data)

    def get_conversations(name):
        print("get_conversations, name = ", str(name))
        return {}

    def update_conversation(name, key, new_state):
        print("update_conversation, name = ", name, ", key = ", key, ", new_state = ", new_state)

    def flush(self):
        print("flush, self = ", self)


#######################################################################################################################
# KEYBOARDS                                                                                                           #
#######################################################################################################################
def get_lang_keyboard():
    lang_keyboard = [
        [
            InlineKeyboardButton(btn["BTN_EN"], callback_data = "lang_EN"),
            InlineKeyboardButton(btn["BTN_RU"], callback_data = "lang_RU"),
        ],
    ]
    keyboard_text = txt["LANG"]
    return keyboard_text, lang_keyboard

def get_lang_help_keyboard():
    lang_help_keyboard = [
        [
            InlineKeyboardButton(btn["BTN_EN"], callback_data = "lang_help_EN"),
            InlineKeyboardButton(btn["BTN_RU"], callback_data = "lang_help_RU"),
        ],
    ]
    keyboard_text = txt["LANG"]
    return keyboard_text, lang_help_keyboard


def get_sell_buy_help_keyboard(lang):
    sell_buy_help_keyboard = [
        [
            InlineKeyboardButton(btn[lang]["BTN_SELL"], callback_data = "sell_buy_help_SELL"),
        ],
        [
            InlineKeyboardButton(btn[lang]["BTN_BUY"], callback_data = "sell_buy_help_BUY"),
        ],
        [
            InlineKeyboardButton(btn[lang]["BTN_HELP"], callback_data = "sell_buy_help_HELP"),
        ],
    ]
    keyboard_text = txt[lang]["WELCOME"]
    return keyboard_text, sell_buy_help_keyboard

def get_buy_help_keyboard(lang, available_limit):
    buy_help_keyboard = [
        [
            InlineKeyboardButton(btn[lang]["BTN_BUY"], callback_data = "buy_help_BUY"),
            InlineKeyboardButton(btn[lang]["BTN_HELP"], callback_data = "buy_help_HELP"),
        ],
    ]
    if available_limit > 1:
        keyboard_text = txt[lang]["WELCOME_CONTACT_OK"].format(available_limit, lim["LIMIT_USER_PHOTO_CNT"])
    elif available_limit == 1:
        keyboard_text = txt[lang]["WELCOME_CONTACT_ONE"].format(lim["LIMIT_USER_PHOTO_CNT"])
    else:
        keyboard_text = txt[lang]["WELCOME_CONTACT_LIMIT"]
    return keyboard_text, buy_help_keyboard

def get_share_contact_keyboard(lang):
    share_contact_keyboard = [
        [
            KeyboardButton(btn[lang]["BTN_CONTACT"], request_contact = True)
        ,]
    ]
    keyboard_text = txt[lang]["CONTACT"].format(backhand_index_pointing_down)
    return keyboard_text, share_contact_keyboard    

def get_moder_keyboard():
    moder_keyboard = [
        [
            InlineKeyboardButton("Parse", callback_data = key),
            InlineKeyboardButton("Snooze", callback_data="2"),
        ],
        [InlineKeyboardButton("Ignore", callback_data="3")],
    ]
    keyboard_text = txt["MODER_START"].format(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S'))
    return keyboard_text, moder_keyboard


#######################################################################################################################
# WORKFLOW                                                                                                            #
#######################################################################################################################

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    """Send a message when the command /start is issued."""
    status, lang_str, _ = get_chat(context)
    if status.startswith("banned"):
        banned()
        return

    # empty /start
    if not context.args:
        # if no language argument passed with /start, then we show the language menu to choose language explicitly
        keyboard_text, lang_keyboard = get_lang_keyboard()
        update.message.reply_text(text = keyboard_text, reply_markup = InlineKeyboardMarkup(lang_keyboard, one_time_keyboard = True))              

    # /start RU or /start EN
    elif context.args[0] in ALLOWED_LANGUAGES:
        # for newbies - choose language based on /start command parameter
        if status in (NEW, PRELANG, DELETED):
            lang(update, context, context.args[0])
        # preserve current lang for lang+ statuses
        elif lang != "":
            lang(update, context, lang_str)
        # status lang+, but lang unknown
        else:
            lang(update, context, context.args[0])

    # /start BS
    else:
        # for newbies - choose language via keyboard
        if status in (NEW, PRELANG, DELETED):
            keyboard_text, lang_keyboard = get_lang_keyboard()
            update.message.reply_text(text = keyboard_text, reply_markup = InlineKeyboardMarkup(lang_keyboard, one_time_keyboard = True))              
        # preserve current lang for lang+ statuses
        elif lang != "":
            lang(update, context, lang_str)
        # status lang+, but lang unknown
        else:
            update.message.reply_text(txt["LANG_ERR"])
            lang(update, context, "EN")


# check if LANG menu has been used
def lang_menu_check(callback_data):
    return callback_data.startswith("lang")

# reaction to the choice of language via language keyboard
def lang_menu(update, context):
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()

    query.data = query.data.replace("lang_", "")

    if query.data in ALLOWED_LANGUAGES:
        # record language constant for this chat if it's been selected via keyboard
        lang(update, context, query.data)
    else:
        update.message.reply_text(txt["LANG_ERR"])
        lang(update, context, "EN")

# assign lang status and proceed according to the workflow
def lang(update, context, lang_string):
    status, _ , active_posts = get_chat(context)
    if status.startswith("banned"):
        banned()
        return

    # setting language for current chat
    context.chat_data["lang"] = lang_string

    # calculating available posts limit
    available_limit = lim["LIMIT_USER_POSTS_CNT"] - active_posts

    # for newbies - upgrade status to LANG and show the SELL_BUY_HELP keyboard
    if status in (NEW, PRELANG, DELETED):
        status = LANG
        context.user_data["status"] = status
        keyboard_text, sell_buy_help_keyboard = get_sell_buy_help_keyboard(lang_string)
        update.effective_message.reply_text(text = keyboard_text, reply_markup = InlineKeyboardMarkup(sell_buy_help_keyboard, one_time_keyboard = True))    

    # changing (or keeping, if current language has been passed on to this proc) language for LANG or TOS statuses, status doesn't change:
    elif status in (LANG, TOS):
        keyboard_text, sell_buy_help_keyboard = get_sell_buy_help_keyboard(lang_string)
        update.effective_message.reply_text(text = keyboard_text, reply_markup = InlineKeyboardMarkup(sell_buy_help_keyboard, one_time_keyboard = True))    

    # for CONTACT status, we show a BUY_HELP keyboard with a message, which depends on available number of posts until limit is reached
    elif status == CONTACT:
        keyboard_text, buy_help_keyboard = get_buy_help_keyboard(lang_string, available_limit)
        update.effective_message.reply_text(text = keyboard_text, reply_markup = InlineKeyboardMarkup(buy_help_keyboard, one_time_keyboard = True))
    # for LIMIT status, we also show a BUY_HELP keyboard, but tell the user that posting is not possible until some posts are deleted
    elif status == LIMIT:
        keyboard_text, buy_help_keyboard = get_buy_help_keyboard(lang_string, 0)
        update.effective_message.reply_text(text = keyboard_text, reply_markup = InlineKeyboardMarkup(buy_help_keyboard, one_time_keyboard = True))
    # no status
    else:
        pass

# /help command
def help(update, context):
    """Send a message when the command /help is issued."""
    status, lang_str, _ = get_chat(context)
    if status.startswith("banned"):
        banned()
        return

    # for newbies, show the language menu to choose language explicitly
    if status in (NEW, PRELANG, DELETED):
        keyboard_text, lang_keyboard = get_lang_help_keyboard()
        update.effective_message.reply_text(text = keyboard_text, reply_markup = InlineKeyboardMarkup(lang_help_keyboard, one_time_keyboard = True))              
    # preserve current lang for lang+ statuses
    elif lang != "":
        lang_help(update, context, lang_str)
    # status lang+, but lang unknown
    else:
        update.effective_message.reply_text(txt["LANG_ERR"])
        lang_help(update, context, "EN")

# check if LANG_HELP menu has been used
def lang_help_menu_check(callback_data):
    return callback_data.startswith("lang_help")

# reaction to LANG_HELP menu
def lang_help_menu(update, context):
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()

    query.data = query.data.replace("lang_help_", "")

    if query.data in ALLOWED_LANGUAGES:
        # record language constant for this chat if it's been selected via keyboard
        lang_help(context, query.data)
    else:
        update.effective_message.reply_text(txt["LANG_ERR"])
        lang(context, "EN")

# show help in a given language and proceed with the workflow
def lang_help(update, context, lang_string):
    status, _ , active_posts = get_chat(context)
    if status.startswith("banned"):
        banned()
        return

    # show help
    update.effective_message.reply_text(msg[lang_string]["HELP"])

    # proceed with the workflow
    lang(update, context, lang_string)


# check if SELL_BUY_HELP keyboard has been used
def sell_buy_help_menu_check(callback_data):
    return callback_data.startswith("sell_buy_help")

# reaction to the SELL_BUY_HELP keyboard
def sell_buy_help_menu(update, context):
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()

    query.data = query.data.replace("sell_buy_help_", "")

    if query.data == "SELL":
        # share the phone # and start posting photos
        keyboard_text, share_contact_keyboard = get_share_contact_keyboard(context.chat_data["lang"])
        update.effective_message.reply_text(text = keyboard_text, reply_markup = ReplyKeyboardMarkup(share_contact_keyboard, one_time_keyboard = True))
    elif query.data == "BUY":
        update.effective_message.reply_text(text = txt[context.chat_data["lang"]]["BUY_START"])
    else:
        update.effective_message.reply_text(text = "UNDER CONSTRUCTION")

# check if BUY_HELP menu has been used
def buy_help_menu_check(callback_data):
    return callback_data.startswith("buy_help")

# reaction to the BUY_HELP keyboard
def buy_help_menu(update, context):
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()

    query.data = query.data.replace("buy_help_", "")

    if query.data == "BUY":
        # share the phone # and start posting photos
        keyboard_text, share_contact_keyboard = get_share_contact_keyboard(context.chat_data["lang"])
        update.callback_query.message.reply_text(text = keyboard_text, reply_markup = ReplyKeyboardMarkup(share_contact_keyboard, one_time_keyboard = True))
    elif query.data == "HELP":
        update.callback_query.message.reply_text(text = txt[context.chat_data["lang"]]["BUY_START"])
    else:
        update.callback_query.message.reply_text(text = "UNDER CONSTRUCTION")





#def echo(update, context):
#    """Echo the user message."""
#    context.bot.sendMessage(ADMINCHATID, text = update.message.to_json())
#    update.message.reply_text(update.message.text)





# handle contact
def contact(update, context):
    contact = update.effective_message.contact
    phone = contact.phone_number
    context.chat_data["phone"] = phone
    update.message.reply_text(txt[context.chat_data["lang"]]["SELL_PHONE_OK"])    

# reacton to a photo sent for moderation
def photo(update, context):
    context.bot.sendMessage(ADMINCHATID, text = "photo: " + update.message.to_json())
    fwd_message = update.message.forward(ADMINCHATID)
    #store the pic file_id in a key-value store in memory for future references to pic (for recognition etc.) 
    key = str(uuid4())
    value = fwd_message.photo[-1].file_id
    context.bot_data[key] = value

    keyboard_text, moder_keyboard = get_moder_keyboard()
    context.bot.sendMessage(ADMINCHATID, text = keyboard_text, reply_markup = InlineKeyboardMarkup(moder_keyboard))          

# check if moder_menu has been used
def moder_menu_check(callback_data):
    return len(callback_data) > 10

# reaction to the moder_keyboard
def moder_menu(update, context):
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()

#    print('key = ', query.data)
#    print('value = ', context.bot_data[query.data])

    pic = context.bot.get_file(context.bot_data[query.data])
    print('pic = ', str(pic))
    b = BytesIO((pic.download_as_bytearray())) #or maybe try getvalue()
    b.seek(0)
    content = b.read()
    #content = base64.b64encode(BytesIO(pic.download_as_bytearray()))
#    context.bot.send_photo(ADMINCHATID, photo = pic.file_id)

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content = content)
    #image = vision.Image()
    #image.source.image_uri = pic.file_path #doesn't work, err code 7 - we're not allowed to access URL on your behalf 
    response = client.label_detection(image = image) #object_localization(image=image)
    print(response.label_annotations)

    s = ''
    for label in response.label_annotations:
        s = s + label.description + ', ' + str(round(label.score*100, 1)) + '%' + '\n\r'

    context.bot.sendMessage(ADMINCHATID, text = s)

    #query.edit_message_text(text=f"Selected option: {query.data}")
    #query.edit_message_text(text=msg.message_id)

def banned(context):
    print("access attempt by a banned user: ", context.user_data)

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    persistence = DummyPersistence()
    updater = Updater(TOKEN, use_context = True, persistence = persistence)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))

    # on noncommand i.e message - echo the message on Telegram
#    dp.add_handler(MessageHandler(Filters.text, echo))

    # log all errors
    dp.add_error_handler(error)

    # handle language menu (after /start command)
    dp.add_handler(CallbackQueryHandler(lang_menu, pattern = lang_menu_check))

    # handle language menu (after /help command)
    dp.add_handler(CallbackQueryHandler(lang_help_menu, pattern = lang_help_menu_check))

    # handle main menu (before CONTACT)
    dp.add_handler(CallbackQueryHandler(sell_buy_help_menu, pattern = sell_buy_help_menu_check))

    # handle main menu (having CONTACT)
    dp.add_handler(CallbackQueryHandler(buy_help_menu, pattern = buy_help_menu_check))





    # handle contact
    dp.add_handler(MessageHandler(Filters.contact, contact))

    # receive photos
    dp.add_handler(MessageHandler(Filters.photo, photo))

    # handle moderator's menu on new photo
    dp.add_handler(CallbackQueryHandler(moder_menu, pattern = moder_menu_check))

    # Start the Bot
    updater.start_webhook(listen="0.0.0.0",
                          port=int(PORT),
                          url_path=TOKEN,
                          webhook_url='https://komunado.herokuapp.com/' + TOKEN)
    #updater.bot.setWebhook('https://komunado.herokuapp.com/' + TOKEN)

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()