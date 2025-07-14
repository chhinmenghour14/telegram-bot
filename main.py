import os
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext
)

# Set your timezone offset here (UTC+7)
UTC_PLUS_7 = timezone(timedelta(hours=7))

TOKEN = os.environ.get("TELEGRAM_TOKEN")

# In-memory storage: {chat_id: [message_data]}
message_store = {}

async def store_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id

    # Extract numbers from all formats
    numbers = []

    # Pattern 1: $20 or $3.79 style
    numbers += re.findall(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)", text)

    # Pattern 2: Khmer style - ទទួលប្រាក់ចំនួន 1.23 ដុល្លារ or បានទទួល 28.80 ដុល្លារ
    numbers += re.findall(r"(?:ទទួល(?:ប្រាក់ចំនួន)?\s*)([0-9]+(?:\.[0-9]{1,2})?)\s*ដុល្លារ", text)

    if not numbers:
        return

    if chat_id not in message_store:
        message_store[chat_id] = []

    message_data = {
        "timestamp": update.message.date,
        "numbers": numbers,
        "text": text
    }
    message_store[chat_id].append(message_data)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("ថ្ងៃនេះ 6:00AM-1:30PM", callback_data="today_morning")],
        [InlineKeyboardButton("ថ្ងៃនេះ 1:30PM-9:00PM", callback_data="today_evening")],
        [InlineKeyboardButton("សប្តាហ៍នេះ", callback_data="week")],
        [InlineKeyboardButton("ខែនេះ", callback_data="month")],
        [InlineKeyboardButton("ជ្រើសរើសពេលវេលាខ្លួនឯង", callback_data="custom")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📅ជ្រើសរើសចន្លោះកាលបរិច្ឆេទសម្រាប់ការគណនាផលបូក:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    now = datetime.now(UTC_PLUS_7)

    if query.data == "today_morning":
        start_dt = now.replace(hour=6, minute=0, second=0, microsecond=0)
        end_dt = now.replace(hour=13, minute=30, second=0, microsecond=0)
        range_name = "ព្រឹកថ្ងៃនេះ (6:00AM-1:30PM)"
    elif query.data == "today_evening":
        start_dt = now.replace(hour=13, minute=30, second=0, microsecond=0)
        end_dt = now.replace(hour=21, minute=0, second=0, microsecond=0)
        range_name = "ល្ងាចថ្ងៃនេះ (1:30PM-9:00PM)"
    elif query.data == "week":
        start_dt = now - timedelta(days=now.weekday())
        start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(days=6, hours=23, minutes=59)
        range_name = "សប្តាហ៍នេះ"
    elif query.data == "month":
        start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_dt = (start_dt + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
        range_name = "ខែនេះ"
    else:
        await query.edit_message_text(
            "📅 សូមផ្ញើចន្លោះកាលបរិច្ឆេទជាទម្រង់:\nឆ្នាំ-ខែ-ថ្ងៃ ម៉ោង:នាទី to ឆ្នាំ-ខែ-ថ្ងៃ ម៉ោង:នាទី\nឧទាហរណ៍: 2025-07-01 00:00 to 2025-07-31 23:59"
        )
        context.user_data["awaiting_custom_range"] = True
        return

    total = 0
    count = 0
    if chat_id in message_store:
        for msg in message_store[chat_id]:
            if start_dt <= msg["timestamp"] <= end_dt:
                for num in msg["numbers"]:
                    try:
                        total += float(num)
                        count += 1
                    except:
                        pass

    start_str = start_dt.strftime("%Y-%m-%d %H:%M")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M")

    if count == 0:
        result = f"🔍 រកមិនឃើញតម្លៃលេខរវាង {range_name} ({start_str} to {end_str})"
    else:
        result = (
            f"📊 *{range_name}*\n"
            f"• រយៈពេល: {start_str} to {end_str}\n"
            f"• សារត្រូវបានយកមកបូក: {count}\n"
            f"• ផលបូកសរុប: {total:.2f}"
        )

    await query.edit_message_text(result, parse_mode="Markdown")

async def handle_custom_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "awaiting_custom_range" not in context.user_data:
        return

    text = update.message.text
    chat_id = update.message.chat_id

    try:
        parts = [p.strip() for p in text.split("to")]
        if len(parts) != 2:
            raise ValueError("Missing 'to' separator")

        start_dt = datetime.strptime(parts[0], "%Y-%m-%d %H:%M").replace(tzinfo=UTC_PLUS_7)
        end_dt = datetime.strptime(parts[1], "%Y-%m-%d %H:%M").replace(tzinfo=UTC_PLUS_7)
    except Exception as e:
        await update.message.reply_text(f"❌ ទម្រង់មិនត្រឹមត្រូវ។ សូមប្រើ: ឆ្នាំ-ខែ-ថ្ងៃ ម៉ោង:នាទី to ឆ្នាំ-ខែ-ថ្ងៃ ម៉ោង:នាទី\nកំហុស: {str(e)}")
        return

    total = 0
    count = 0
    if chat_id in message_store:
        for msg in message_store[chat_id]:
            if start_dt <= msg["timestamp"] <= end_dt:
                for num in msg["numbers"]:
                    try:
                        total += float(num)
                        count += 1
                    except:
                        pass

    start_str = start_dt.strftime("%Y-%m-%d %H:%M")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M")

    if count == 0:
        result = f"🔍 រកមិនឃើញតម្លៃលេខរវាង {start_str} and {end_str}"
    else:
        result = (
            f"📊 *ចន្លោះកាលបរិច្ឆេទ*\n"
            f"• រយៈពេល: {start_str} to {end_str}\n"
            f"• សារត្រូវបានយកមកបូក: {count}\n"
            f"• ផលបូកសរុប: {total:.2f}"
        )

    await update.message.reply_text(result, parse_mode="Markdown")
    del context.user_data["awaiting_custom_range"]

# Dummy server for Render port binding requirement
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"✅ Bot is alive!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('', port), HealthCheckHandler)
    server.serve_forever()

if __name__ == "__main__":
    # Start dummy web server in a separate thread
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, store_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_range))

    print("Bot is running...")
    app.run_polling()
