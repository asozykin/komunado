"""
Simple Bot to reply to Telegram messages taken from the python-telegram-bot examples.
Deployed using heroku.
Example taken from: liuhh02 https://medium.com/@liuhh02
"""

import logging
import os
import base64
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    """Send a message when the command /start is issued."""
    #print(context.message)
    context.bot.sendMessage(ADMINCHATID, text = update.message.to_json())
    update.message.reply_text('Hi!')

def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')

#def echo(update, context):
#    """Echo the user message."""
#    context.bot.sendMessage(ADMINCHATID, text = update.message.to_json())
#    update.message.reply_text(update.message.text)

def photo(update, context):
    context.bot.sendMessage(ADMINCHATID, text="photo: " + update.message.to_json())
    fwd_message = update.message.forward(ADMINCHATID)
    #store the pic file_id in a key-value store in memory for future references to pic (for recognition etc.) 
    key = str(uuid4())
    value = fwd_message.photo[-1].file_id
    context.bot_data[key] = value

    buttons = [
        [
            InlineKeyboardButton("Parse", callback_data = key),
            InlineKeyboardButton("Snooze", callback_data="2"),
        ],
        [InlineKeyboardButton("Ignore", callback_data="3")],
    ]

    context.bot.sendMessage(ADMINCHATID, text="What to do with that photo?", reply_markup=InlineKeyboardMarkup(buttons))

def button(update, context):
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

    # handle buttons
    dp.add_handler(CallbackQueryHandler(button))

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