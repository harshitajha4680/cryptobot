import os
import asyncio
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters
from time import sleep

# Setup logging
logging.basicConfig(level=logging.INFO)

# Constants
BOT_USERNAME = 'xyz'
BOT_TOKEN = os.getenv('BOT_TOKEN')  # Load token from environment variable
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# Check for token
if BOT_TOKEN is None:
    raise ValueError("BOT_TOKEN environment variable is not set.")

# Conversation states
MAIN_MENU, CHOOSING_CRYPTO, CHOOSING_CURRENCY, TYPING_SEARCH, COMPARE_SELECTION = range(5)

# Supported currencies
SUPPORTED_CURRENCIES = ['usd', 'eur', 'gbp', 'jpy', 'aud', 'cad', 'chf', 'cny', 'inr']

# API HELPER FUNCTIONS
def make_api_request(url, params=None):
    for attempt in range(5):  # Retry logic for API requests
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raise an error for bad responses
            return response.json()
        except requests.exceptions.HTTPError as err:
            logging.warning(f"HTTP error occurred: {err}")
            sleep(2)  # Wait before retrying
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            break
    return None

def get_top_cryptos(limit=100):
    params = {
        'vs_currency': 'usd',
        'order': 'market_cap_desc',
        'per_page': limit,
        'page': 1,
        'sparkline': False
    }
    return make_api_request(f"{COINGECKO_API_URL}/coins/markets", params)

def get_trending_cryptos():
    return make_api_request(f"{COINGECKO_API_URL}/search/trending")

def get_crypto_details(crypto_id: str, currency: str = 'usd'):
    params = {'ids': crypto_id, 'vs_currencies': currency, 'include_24hr_change': 'true', 'include_market_cap': 'true'}
    return make_api_request(f"{COINGECKO_API_URL}/simple/price", params)

# COMMAND HANDLER FUNCTIONS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await show_main_menu(update, context)
    return MAIN_MENU

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "Welcome to the Crypto Price Bot!\n\n"
        "Commands:\n"
        "/start - Show main menu\n"
        "/help - Show this help message\n"
        "/convert - Convert Currencies From One To Another\n"
        "/pricehistory - Get historical prices\n"
        "/news - Get latest crypto news\n"
    )
    await update.message.reply_text(help_text)

# Menu Display and Button Handlers
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, is_comparing: bool = False) -> None:
    keyboard = [
        [InlineKeyboardButton("Top 100 Cryptocurrencies", callback_data='top100')],
        [InlineKeyboardButton("Trending Cryptocurrencies", callback_data='trending')],
        [InlineKeyboardButton("Search Cryptocurrency", callback_data='search')],
        [InlineKeyboardButton("Quit", callback_data='quit')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "Welcome to the Crypto Price Bot! What would you like to do?" if not is_comparing else "Select a cryptocurrency to compare."
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def show_crypto_list(update: Update, context: ContextTypes.DEFAULT_TYPE, cryptos, title) -> None:
    keyboard = []
    for i in range(0, len(cryptos), 2):
        row = []
        for crypto in cryptos[i:i+2]:
            name = crypto.get('name', 'Unknown')
            symbol = crypto.get('symbol', 'Unknown')
            crypto_id = crypto.get('id', 'unknown')
            row.append(InlineKeyboardButton(f"{name} ({symbol.upper()})", callback_data=f"crypto:{crypto_id}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(title, reply_markup=reply_markup)

async def show_crypto_details(update: Update, context: ContextTypes.DEFAULT_TYPE, crypto_id: str, currency: str) -> None:
    details = get_crypto_details(crypto_id, currency)
    if details:
        price = details.get(currency, 'N/A')
        change_24h = details.get(f'{currency}_24h_change', 'N/A')
        market_cap = details.get(f'{currency}_market_cap', 'N/A')
        trading_volume = details.get(f'{currency}_24h_vol', 'N/A')

        message = (
            f"💰 {crypto_id.capitalize()} ({currency.upper()})\n"
            f"Price: {price} {currency.upper()}\n"
            f"24h Change: {change_24h}%\n"
            f"Market Cap: {market_cap} {currency.upper()}\n"
            f"24h Trading Volume: {trading_volume} {currency.upper()}\n\n"
        )

        await update.callback_query.edit_message_text(message)
        keyboard = [
            [InlineKeyboardButton("Compare with another Cryptocurrency", callback_data='compare_selection')],
            [InlineKeyboardButton("Main Menu", callback_data='main_menu')],
            [InlineKeyboardButton("Quit", callback_data='quit')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("Select an option:", reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text("🚫 Unable to retrieve cryptocurrency details.")

async def show_currency_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton(currency.upper(), callback_data=f"currency:{currency}")]
                for currency in SUPPORTED_CURRENCIES]
    keyboard.append([InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text('Choose a currency:', reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'main_menu':
        await show_main_menu(update, context)
        return MAIN_MENU
    elif query.data == 'top100':
        await query.edit_message_text("Fetching top cryptocurrencies, please wait...")
        cryptos = get_top_cryptos()
        await show_crypto_list(update, context, cryptos, "Top 100 Cryptocurrencies:")
        return CHOOSING_CRYPTO
    elif query.data == 'quit':
        await query.edit_message_text("You can return to the main menu anytime by using /start.")
        return MAIN_MENU
    elif query.data == 'trending':
        await query.edit_message_text("Fetching trending cryptocurrencies, please wait...")
        cryptos = get_trending_cryptos()
        await show_crypto_list(update, context, cryptos, "Trending Cryptocurrencies:")
        return CHOOSING_CRYPTO
    elif query.data == 'search':
        await query.edit_message_text("Please enter the name of the cryptocurrency you want to check:")
        return TYPING_SEARCH
    elif query.data.startswith('crypto:'):
        context.user_data['crypto'] = query.data.split(':')[1]
        await show_currency_options(update, context)
        return CHOOSING_CURRENCY
    elif query.data.startswith('currency:'):
        currency = query.data.split(':')[1]
        crypto_id = context.user_data.get('crypto', 'bitcoin')
        await show_crypto_details(update, context, crypto_id, currency)
        return COMPARE_SELECTION
    elif query.data == 'compare_selection':
        crypto_id = context.user_data.get('crypto')
        if not crypto_id:
            await query.edit_message_text("Please select a cryptocurrency before comparing.")
            return

        await query.edit_message_text("Fetching top 100 currencies for comparison, please wait...")
        cryptos = get_top_cryptos()
        await show_crypto_list(update, context, cryptos, f"Compare {crypto_id} with another currency:")
        return CHOOSING_CURRENCY
    else:
        await query.edit_message_text("Invalid selection. Returning to main menu.")
        await show_main_menu(update, context)
        return MAIN_MENU

# **New Function for Price History**
async def price_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    crypto = context.args[0].lower() if context.args else 'bitcoin'
    historical_prices = get_historical_prices(crypto)
    await update.message.reply_text(f"Price history for {crypto.capitalize()}:\n{historical_prices}")

def get_historical_prices(crypto: str):
    # Replace with a function that fetches historical prices
    # This is a placeholder implementation
    return "Historical prices are not yet implemented."

# **New Function for Crypto News**
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news = get_crypto_news()
    await update.message.reply_text(f"Latest crypto news:\n{news}")

def get_crypto_news():
    # Replace with a function that fetches crypto news
    # This is a placeholder implementation
    return "Latest crypto news are not yet implemented."

# MAIN FUNCTION
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("pricehistory", price_history_command))
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CallbackQueryHandler(button_click))

    # Fallback for text input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_click))

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
