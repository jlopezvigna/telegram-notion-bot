from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from notion_client import Client
import logging
from dotenv import load_dotenv
import os

load_dotenv()  # take environment variables from .env.
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
BOT_TOKEN = os.getenv('BOT_TOKEN')
USERNAME_ID = int(os.getenv('USERNAME_ID'))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename='bot.log',
    filemode='a'
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

TITLE, PRIORITY, TAG, STATUS, DESCRIPTION = range(5)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks the user about title."""
    await update.message.reply_text(
        "Hi! I'm your Bot. I will hold a conversation with you. "
        "Send /cancel to stop talking to me.\n\n"
        "What's the title's ticket?"
    )

    return TITLE


async def title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the title and asks about their priority."""
    context.user_data['title'] = update.message.text
    logger.info("Task Title: %s", update.message.text)
    reply_keyboard = [["Low", "Medium", "High"]]
    await update.message.reply_text(
        "What's the priority level?".format(update.message.text),
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Low, Medium, or High?"
        ),
    )

    return PRIORITY


async def priority(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the priority level and asks for a tag."""
    context.user_data['priority'] = update.message.text
    logger.info("Task Priority: %s", update.message.text)
    reply_keyboard = [["Personal", "Work", "Health"]]
    await update.message.reply_text(
        "Got it! Now, please choose a tag for your task.",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Personal, Work, or Health?"
        ),
    )

    return TAG


async def remember_priorities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply_keyboard = [["Low", "Medium", "High"]]
    await update.message.reply_text(
        "You should choose or write one of this options".format(update.message.text),
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Low, Medium, or High?"
        ),
    )

    return


async def tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the tag and asks for the status."""
    context.user_data['tag'] = update.message.text
    logger.info("Task Tag: %s", update.message.text)
    reply_keyboard = [["New", "Active", "Resolved"]]
    await update.message.reply_text(
        "Great choice! Now, please choose a status for your task.",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="New, Active, or Resolved?"
        ),
    )

    return STATUS


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the status and asks for a description."""
    context.user_data['status'] = update.message.text
    logger.info("Task Status: %s", update.message.text)
    await update.message.reply_text(
        "Now, please provide a description for your task, or send /skip."
    )

    return DESCRIPTION


async def create_notion_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores the task in Notion."""
    notion = Client(auth=NOTION_TOKEN)
    try:
        notion.pages.create(
            **{
                "parent": {
                    "type": "database_id",
                    "database_id": NOTION_DATABASE_ID
                },
                "properties": {
                    # "Date": {
                    #     "date": {
                    #         "start": "2024-03-27",
                    #     }
                    # },
                    "Status": {
                        "select": {
                            "name": context.user_data['status'],
                        }
                    },
                    "Priority": {
                        "select": {
                            "name": context.user_data['priority'],
                        }
                    },
                    "Tags": {
                        "multi_select": [
                            {
                                "name": context.user_data['tag'],
                            }
                        ]
                    },
                    "Name": {
                        "title": [
                            {
                                "text": {
                                    "content": context.user_data['title'],
                                },
                            }
                        ]
                    },
                    "Description": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": context.user_data['description'],
                                },
                            }
                        ]
                    }
                }
            }
        )
        logger.info("Success created item")
        await update.message.reply_text("Your task has been created.")
    except Exception as error:
        await update.message.reply_text("Something went wrong. Please try again.")
        logger.error("Error in creating item: %s || %s", error, type(error).__name__)


async def description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the description task and ends the conversation."""
    context.user_data['description'] = update.message.text
    logger.info("Task Description: %s", update.message.text)
    await create_notion_entry(update, context)

    return ConversationHandler.END


async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Skips the description and  ends the conversation."""
    context.user_data['description'] = ""
    logger.info("the task ** %s ** did not have description.", context.user_data['title'])
    await create_notion_entry(update, context)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        "Bye! I hope we can talk again some day.", reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # Add conversation handler with the states PRIORITY, TAG, STATUS and DESCRIPTION
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start, filters=filters.User(USERNAME_ID))],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, title)],
            PRIORITY: [
                MessageHandler(filters.Regex("^(Low|Medium|High)$"), priority),
                MessageHandler(filters.TEXT & ~filters.COMMAND, remember_priorities)
            ],
            TAG: [MessageHandler(filters.Regex("^(Personal|Work|Health)$"), tag)],
            STATUS: [MessageHandler(filters.Regex("^(New|Active|Resolved)$"), status)],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, description),
                CommandHandler("skip", skip_description),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
