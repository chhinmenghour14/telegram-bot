import os
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta, timezone
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext
)
from telegram.constants import ParseMode

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
    elif query.data == "custom":
        await query.edit_message_text(
            "📅 សូមជ្រើសរើសថ្ងៃចាប់ផ្តើម:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ជ្រើសថ្ងៃ", callback_data="start_date_picker")]
            ])
        )
        context.user_data["date_range_stage"] = "start_date"
        return
    else:
        await query.edit_message_text("❌ ជម្រើសមិនត្រឹមត្រូវ។")
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

    await query.edit_message_text(result, parse_mode=ParseMode.MARKDOWN)

async def date_picker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "start_date_picker":
        await query.edit_message_text(
            "📅 សូមផ្ញើថ្ងៃចាប់ផ្តើមជាទម្រង់:\nឆ្នាំ-ខែ-ថ្ងៃ\nឧទាហរណ៍: 2025-07-01"
        )
        context.user_data["date_range_stage"] = "start_date"
    elif query.data == "end_date_picker":
        await query.edit_message_text(
            "📅 សូមផ្ញើថ្ងៃបញ្ចប់ជាទម្រង់:\nឆ្នាំ-ខែ-ថ្ងៃ\nឧទាហរណ៍: 2025-07-31"
        )
        context.user_data["date_range_stage"] = "end_date"

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # First store the message if it contains numbers
    await store_message(update, context)
    
    # Then handle date/time selection if in progress
    if "date_range_stage" not in context.user_data:
        return

    text = update.message.text.strip()
    stage = context.user_data["date_range_stage"]

    try:
        if stage == "start_date":
            # Validate date format
            datetime.strptime(text, "%Y-%m-%d")
            context.user_data["start_date"] = text
            await update.message.reply_text(
                "⏰ ឥឡូវសូមផ្ញើម៉ោងចាប់ផ្តើម (HH:MM):\nឧទាហរណ៍: 08:30",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="06:00"), KeyboardButton(text="12:00")],
                        [KeyboardButton(text="13:30"), KeyboardButton(text="18:00")],
                        [KeyboardButton(text="00:00"), KeyboardButton(text="23:59")]
                    ],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
            )
            context.user_data["date_range_stage"] = "start_time"

        elif stage == "start_time":
            # Validate time format
            datetime.strptime(text, "%H:%M")
            context.user_data["start_time"] = text
            full_start = f"{context.user_data['start_date']} {text}"
            context.user_data["full_start"] = datetime.strptime(full_start, "%Y-%m-%d %H:%M").replace(tzinfo=UTC_PLUS_7)
            
            # Ask for end date
            await update.message.reply_text(
                "📅 សូមផ្ញើថ្ងៃបញ្ចប់ជាទម្រង់:\nឆ្នាំ-ខែ-ថ្ងៃ\nឧទាហរណ៍: 2025-07-31",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="ជ្រើសថ្ងៃ")]],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
            )
            context.user_data["date_range_stage"] = "end_date"

        elif stage == "end_date":
            # Validate date format
            datetime.strptime(text, "%Y-%m-%d")
            context.user_data["end_date"] = text
            await update.message.reply_text(
                "⏰ ឥឡូវសូមផ្ញើម៉ោងបញ្ចប់ (HH:MM):\nឧទាហរណ៍: 17:30",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="06:00"), KeyboardButton(text="12:00")],
                        [KeyboardButton(text="13:30"), KeyboardButton(text="18:00")],
                        [KeyboardButton(text="00:00"), KeyboardButton(text="23:59")]
                    ],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
            )
            context.user_data["date_range_stage"] = "end_time"

        elif stage == "end_time":
            # Validate time format
            datetime.strptime(text, "%H:%M")
            context.user_data["end_time"] = text
            full_end = f"{context.user_data['end_date']} {text}"
            context.user_data["full_end"] = datetime.strptime(full_end, "%Y-%m-%d %H:%M").replace(tzinfo=UTC_PLUS_7)
            
            # Calculate the sum
            total = 0
            count = 0
            chat_id = update.message.chat_id
            start_dt = context.user_data["full_start"]
            end_dt = context.user_data["full_end"]
            
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

            await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
            
            # Clean up
            for key in ["date_range_stage", "start_date", "start_time", "full_start", 
                       "end_date", "end_time", "full_end"]:
                if key in context.user_data:
                    del context.user_data[key]

    except ValueError as e:
        error_msg = ""
        if "time data" in str(e):
            if "date" in stage:
                error_msg = "❌ ទម្រង់ថ្ងៃមិនត្រឹមត្រូវ។ សូមបញ្ចូលជា ឆ្នាំ-ខែ-ថ្ងៃ (ឧទាហរណ៍: 2025-07-15)"
            else:
                error_msg = "❌ ទម្រង់ម៉ោងមិនត្រឹមត្រូវ។ សូមបញ្ចូលជា HH:MM (ឧទាហរណ៍: 14:30)"
        else:
            error_msg = "❌ ទម្រង់មិនត្រឹមត្រូវ។ សូមព្យាយាមម្តងទៀត។"
        
        await update.message.reply_text(error_msg)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write("✅ Bot is alive!".encode('utf-8'))
    
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('', port), HealthCheckHandler)
    server.serve_forever()

if __name__ == "__main__":
    # Start web server in a separate thread
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CallbackQueryHandler(date_picker_handler, pattern="^start_date_picker$|^end_date_picker$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    print("Bot is running...")
    app.run_polling()