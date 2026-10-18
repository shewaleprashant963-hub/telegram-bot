import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Configuration
BOT_TOKEN = "8956034040:AAHJMuE1p-2lcEC7IWo6xs6Qa_U5E9DCPE0"
ADMIN_USER_ID = 5765053762
DB_PATH = "college_resources.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ----------------- Database Setup ----------------- #

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            file_id TEXT NOT NULL,
            file_name TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_document(class_name, subject, category, title, file_id, file_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO documents (class_name, subject, category, title, file_id, file_name) VALUES (?, ?, ?, ?, ?, ?)",
        (class_name.strip(), subject.strip(), category.strip(), title.strip(), file_id, file_name),
    )
    last_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return last_id

def delete_document_by_id(doc_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    changes = conn.total_changes
    conn.commit()
    conn.close()
    return changes > 0

def get_classes():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT class_name FROM documents ORDER BY class_name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_subjects(class_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT subject FROM documents WHERE class_name = ? ORDER BY subject ASC", (class_name,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_files_by_filter(class_name, subject, category):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title FROM documents WHERE class_name = ? AND subject = ? AND LOWER(category) = LOWER(?) ORDER BY id DESC",
        (class_name, subject, category),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_file_by_id(doc_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, title FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    return row

# ----------------- User Navigation Handlers ----------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    classes = get_classes()
    if not classes:
        msg = (
            "👋 **Welcome to the SSVPS College Resource Bot!**\n\n"
            "No resources have been added yet.\n\n"
            "Admins, upload files with this caption:\n"
            "`Class | Subject | Category | Title`\n\n"
            "*(Example: Class 11 | P.C.M.B | Notes | Chapter 1)*"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    keyboard = [[InlineKeyboardButton(cls, callback_data=f"cls:{cls}")] for cls in classes]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎓 **Select your Class:**",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "nav:home":
        classes = get_classes()
        keyboard = [[InlineKeyboardButton(cls, callback_data=f"cls:{cls}")] for cls in classes]
        await query.edit_message_text(
            "🎓 **Select your Class:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return

    if data.startswith("cls:"):
        class_name = data.split("cls:")[1]
        subjects = get_subjects(class_name)
        keyboard = [[InlineKeyboardButton(sub, callback_data=f"sub:{class_name}:{sub}")] for sub in subjects]
        keyboard.append([InlineKeyboardButton("⬅️ Back to Classes", callback_data="nav:home")])
        await query.edit_message_text(
            f"📚 **Class:** {class_name}\nSelect a Subject:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return

    if data.startswith("sub:"):
        _, class_name, subject = data.split(":", 2)
        
        compulsory_categories = ["Notes", "Question Banks", "Unit Test", "Half Semester", "Annual Exam", "Other"]
        
        keyboard = []
        for cat in compulsory_categories:
            keyboard.append([InlineKeyboardButton(f"📁 {cat}", callback_data=f"cat:{class_name}:{subject}:{cat}")])
            
        keyboard.append([InlineKeyboardButton("⬅️ Back to Subjects", callback_data=f"cls:{class_name}")])
        
        await query.edit_message_text(
            f"📂 **{class_name} ➜ {subject}**\nSelect Category:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return

    if data.startswith("cat:"):
        _, class_name, subject, category = data.split(":", 3)
        files = get_files_by_filter(class_name, subject, category)
        
        if not files:
            await context.bot.answer_callback_query(
                callback_query_id=query.id, 
                text="⚠️ No files uploaded in this category yet!", 
                show_alert=True
            )
            return

        keyboard = [[InlineKeyboardButton(f"📄 {title} (ID: {doc_id})", callback_data=f"get:{doc_id}")] for doc_id, title in files]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"sub:{class_name}:{subject}")])
        
        await query.edit_message_text(
            f"📄 **{category} ({subject})**\nClick to download:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return

    if data.startswith("get:"):
        doc_id = int(data.split("get:")[1])
        record = get_file_by_id(doc_id)
        if record:
            file_id, title = record
            await query.message.reply_text(f"⏳ Sending *{title}*...", parse_mode="Markdown")
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=file_id,
                caption=f"✅ {title}",
            )
        else:
            await query.message.reply_text("❌ File not found or has been deleted.")

# ----------------- Admin File Upload & Delete ----------------- #

async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_USER_ID:
        return

    document = update.message.document
    caption = update.message.caption

    if not caption or "|" not in caption:
        await update.message.reply_text(
            "⚠️ **Format missing in caption.**\n\n"
            "Format: `Class | Subject | Category | Title`\n"
            "Example: `Class 11 | Physics | Question Banks | Chapter 1 MCQ`",
            parse_mode="Markdown",
        )
        return

    parts = [p.strip() for p in caption.split("|")]
    if len(parts) < 4:
        await update.message.reply_text("⚠️ Please provide all 4 parts: `Class | Subject | Category | Title`")
        return

    class_name, subject, category, title = parts[0], parts[1], parts[2], parts[3]
    file_id = document.file_id
    file_name = document.file_name or "document.pdf"

    doc_id = add_document(class_name, subject, category, title, file_id, file_name)
    await update.message.reply_text(
        f"✅ **Saved to Database!**\n\n"
        f"🎓 **Class:** {class_name}\n"
        f"📚 **Subject:** {subject}\n"
        f"📂 **Category:** {category}\n"
        f"📄 **Title:** {title}\n\n"
        f"🗑️ *To delete this file later, send:* `/delete {doc_id}`",
        parse_mode="Markdown",
    )

async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_USER_ID:
        return

    if not context.args:
        await update.message.reply_text("⚠️ Please provide the File ID.\nExample: `/delete 1`")
        return

    try:
        doc_id = int(context.args[0])
        success = delete_document_by_id(doc_id)
        if success:
            await update.message.reply_text(f"✅ File ID {doc_id} has been successfully deleted from the bot.")
        else:
            await update.message.reply_text(f"❌ File ID {doc_id} not found in database.")
    except ValueError:
        await update.message.reply_text("⚠️ Invalid ID format. Please send a number.")

# ----------------- Main App ----------------- #

def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("delete", delete_file))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND, handle_document_upload))

    print("College Resource Bot is online with Delete Option...")
    app.run_polling()

if __name__ == "__main__":
    main()