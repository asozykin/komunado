"""
KomuNado bot
"""
# -*- coding: UTF-8 -*-

import logging
import os
import base64
import json
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, CallbackContext, Filters
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
backhand_index_pointing_down = u'\U0001F447'

# load config
with open('config.json') as f:
    config = json.load(f)

# shortcuts
btn = config["buttons"]
txt = config["messagetext"]
lim = config["limits"]

# keyboards
def get_lang_keyboard():
    lang_keyboard = [
        [
            InlineKeyboardButton(btn["BTN_EN"], callback_data = "lang_EN"),
            InlineKeyboardButton(btn["BTN_RU"], callback_data = "lang_RU"),
        ],
    ]
    keyboard_text = txt["LANG"]
    return keyboard_text, lang_keyboard

def get_sell_or_buy_keyboard(lang):
    sell_or_buy_keyboard = [
        [
            InlineKeyboardButton(btn[lang]["BTN_SELL"], callback_data = "sell_or_buy_SELL"),
            InlineKeyboardButton(btn[lang]["BTN_BUY"], callback_data = "sell_or_buy_BUY"),
        ],
    ]
    keyboard_text = txt[lang]["SELL_OR_BUY"]
    return keyboard_text, sell_or_buy_keyboard

def get_share_contact_keyboard(lang):
    share_contact_keyboard = [
        [
            KeyboardButton(btn[lang]["BTN_CONTACT"], request_contact = True)
        ,]
    ]
    keyboard_text = txt[lang]["SELL_START"].format(backhand_index_pointing_down)
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

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    """Send a message when the command /start is issued."""
    # Language selection and welcome message
    if not context.args:
        # if no language argument passed with /start, then we show the language menu to choose language explicitly
        keyboard_text, lang_keyboard = get_lang_keyboard()
        update.message.reply_text(text = keyboard_text, reply_markup = InlineKeyboardMarkup(lang_keyboard, one_time_keyboard = True))              

    elif context.args[0] in {"RU", "EN"}:
        # record language constant for this chat if it's been passed with /start command
        context.chat_data["language"] = context.args[0]
        update.message.reply_text(txt[context.chat_data["language"]]["WELCOME"])

    else:
        context.chat_data["language"] = "EN"
        update.message.reply_text(txt["LANG_ERR"] + ' ' + config["messagetext"][context.chat_data["language"]]["WELCOME"])

# check if LANGUAGE menu has been used OR empty callback data has arrived
def lang_menu_check(callback_data):
    return (len(callback_data) == 0) or callback_data.startswith("lang")

# reaction to the choice of language via language keyboard
def lang_menu(update, context):
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()

    if query.data in {"RU", "EN"}:
        # record language constant for this chat if it's been selected via keyboard
        context.chat_data["language"] = query.data        
        query.edit_message_text(txt[context.chat_data["language"]]["WELCOME"])

    else:
        context.chat_data["language"] = "EN"
        query.edit_message_text("Bad language parameter, switching to English. " + txt[context.chat_data["language"]]["WELCOME"])

    keyboard_text, sell_or_buy_keyboard = get_sell_or_buy_keyboard(context.chat_data["language"])
    update.callback_query.message.reply_text(text = keyboard_text, reply_markup = InlineKeyboardMarkup(sell_or_buy_keyboard, one_time_keyboard = True))    

# check if SELL/BUY menu has been used
def sell_or_buy_menu_check(callback_data):
    return callback_data.startswith("sell_or_buy")

# reaction to the choice of SELL or BUY use-case
def sell_or_buy_menu(update, context):
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()

    if query.data == "SELL":
        # share the phone # and start posting photos
        keyboard_text, share_contact_keyboard = get_share_contact_keyboard(context.chat_data["language"])
        update.callback_query.message.reply_text(text = keyboard_text, reply_markup = ReplyKeyboardMarkup(share_contact_keyboard, one_time_keyboard = True))
    elif query.data == "BUY":
        update.callback_query.message.reply_text(text = txt[context.chat_data["language"]]["BUY_START"])
    else:
        update.callback_query.message.reply_text(text = "UNDER CONSTRUCTION")

def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')

#def echo(update, context):
#    """Echo the user message."""
#    context.bot.sendMessage(ADMINCHATID, text = update.message.to_json())
#    update.message.reply_text(update.message.text)

# handle phone number
def contact(update, context):
    contact = update.effective_message.contact
    phone = contact.phone_number
    context.chat_data["phone"] = phone
    update.message.reply_text(txt[context.chat_data["language"]]["SELL_PHONE_OK"])    

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

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))

    # on noncommand i.e message - echo the message on Telegram
#    dp.add_handler(MessageHandler(Filters.text, echo))

    # log all errors
    dp.add_error_handler(error)

    # receive photos
    dp.add_handler(MessageHandler(Filters.photo, photo))

    # handle language menu (after /start command)
    dp.add_handler(CallbackQueryHandler(languagemenu, pattern = languagemenu_check))

    # handle main menu
    dp.add_handler(CallbackQueryHandler(sellbuymenu, pattern = sellbuymenu_check))

    # handle phone number
    dp.add_handler(MessageHandler(Filters.contact, contact))

    # handle moderator's menu on new photo
    dp.add_handler(CallbackQueryHandler(modermenu, pattern = modermenu_check))

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