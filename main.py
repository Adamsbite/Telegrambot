import os
import logging
import json
from datetime import datetime
import asyncio
from typing import Optional, List, Dict

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import aiohttp
import motor.motor_asyncio

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram message max length (using a safe value)
MAX_MESSAGE_LENGTH = 4000

async def send_split_message(update: Update, text: str, parse_mode: Optional[str] = None) -> None:
    """
    Splits long text into multiple messages and sends them.
    """
    for i in range(0, len(text), MAX_MESSAGE_LENGTH):
        chunk = text[i:i+MAX_MESSAGE_LENGTH]
        await update.message.reply_text(chunk, parse_mode=parse_mode)

# Initialize MongoDB connection
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client.productivity_bot
notes_collection = db.notes
tasks_collection = db.tasks

class OllamaClient:
    def __init__(self, base_url: str = "http://ollama:11434"):
        self.base_url = base_url
        # Strict system prompt: return ONLY the final answer with bullet points.
        self.system_prompt = (
            "You are a direct response assistant. ONLY provide the final answer without any internal thinking, "
            "reasoning, or monologue. Do not include any phrases like 'thinking', 'analysis', or 'I think'. "
            "Format your final answer as bullet points with each item preceded by an emoji (e.g., 🔹). "
            "Return only the final answer."
        )

    async def check_connection(self) -> bool:
        """🔌 Check if Ollama service is available."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=10)) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Ollama connection check failed: {e}")
            return False

    async def generate_response(self, prompt: str) -> Optional[str]:
        """🤖 Generate a direct response using the provided prompt."""
        try:
            formatted_prompt = f"{self.system_prompt}\n\nUser Request: {prompt}\n\nDirect Response:"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": "deepseek-r1:1.5b",
                        "prompt": formatted_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9,
                            "num_predict": 256
                        }
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status != 200:
                        logger.error(f"Ollama API error: Status {response.status}")
                        return None
                    result = await response.json()
                    return result.get('response', '').strip()
        except asyncio.TimeoutError:
            logger.error("Ollama API timeout")
            return None
        except Exception as e:
            logger.error(f"Error calling Ollama API: {e}")
            return None

# Initialize Ollama client
ollama_client = OllamaClient()

async def check_services() -> bool:
    """🔍 Check if required services are running."""
    try:
        await client.admin.command('ping')
        ollama_available = await ollama_client.check_connection()
        return ollama_available
    except Exception as e:
        logger.error(f"Service check failed: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """💬 Send welcome message when /start is issued."""
    welcome_message = """
🌟 *Welcome to your Productivity Assistant!* 🌟

Available commands:
- `/note [text]` 📝: Save a note
- `/task [text]` ✅: Add a task
- `/list` 📋: View all items
- `/search [query]` 🔍: Search items (bullet points)
- `/summary` 📊: Get summary (bullet points)
- `/query [text]` 🤖: Ask any general question and get a final answer
- `/summarize_meeting` 🗣️: Summarize a meeting transcript from a voice message
- `/delete_tasks` 🗑️: Delete all tasks
- `/delete_notes` 🗑️: Delete all notes
- `/help` ❓: Show this message

*Examples:*
1. `/note Call John about project`
2. `/task Submit report by Friday`
3. `/query What is the capital of France?`

Type `/help` anytime for assistance!
    """
    await send_split_message(update, welcome_message, parse_mode="Markdown")

async def save_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """📝 Save a note."""
    try:
        if not context.args:
            await send_split_message(update, "❌ Please add note text\nExample: `/note Call John`", parse_mode="Markdown")
            return
        note = {
            'user_id': update.effective_user.id,
            'text': ' '.join(context.args),
            'timestamp': datetime.utcnow()
        }
        await notes_collection.insert_one(note)
        await send_split_message(update, "✅ *Note saved!* Use `/list` to view all.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error saving note: {e}")
        await send_split_message(update, "❌ Error saving note. Please try again.", parse_mode="Markdown")

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """✅ Add a task."""
    try:
        if not context.args:
            await send_split_message(update, "❌ Please add task text\nExample: `/task Buy groceries`", parse_mode="Markdown")
            return
        task = {
            'user_id': update.effective_user.id,
            'text': ' '.join(context.args),
            'status': 'pending',
            'timestamp': datetime.utcnow()
        }
        await tasks_collection.insert_one(task)
        await send_split_message(update, "✅ *Task added!* Use `/list` to view all.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error adding task: {e}")
        await send_split_message(update, "❌ Error adding task. Please try again.", parse_mode="Markdown")

async def list_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """📋 List all items."""
    try:
        user_id = update.effective_user.id
        notes = await notes_collection.find({'user_id': user_id}).sort('timestamp', -1).to_list(length=None)
        tasks = await tasks_collection.find({'user_id': user_id}).sort('timestamp', -1).to_list(length=None)
        if not notes and not tasks:
            await send_split_message(update, "📝 No items yet. Add with `/note` or `/task`", parse_mode="Markdown")
            return
        response = ["📝 *Your Items:*\n"]
        if notes:
            response.append("*Notes:*")
            for i, note in enumerate(notes, 1):
                date = note['timestamp'].strftime('%Y-%m-%d')
                response.append(f"🔹 {i}. [{date}] {note['text']}")
            response.append("")
        if tasks:
            response.append("*Tasks:*")
            for i, task in enumerate(tasks, 1):
                date = task['timestamp'].strftime('%Y-%m-%d')
                status = "✅" if task['status'] == 'completed' else "⏳"
                response.append(f"🔹 {i}. [{date}] {status} {task['text']}")
        await send_split_message(update, "\n".join(response), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error listing items: {e}")
        await send_split_message(update, "❌ Error retrieving items. Please try again.", parse_mode="Markdown")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🔍 Search items and return bullet-point results."""
    try:
        if not context.args:
            await send_split_message(update, "❌ Please add search text\nExample: `/search project`", parse_mode="Markdown")
            return
        query = ' '.join(context.args)
        user_id = update.effective_user.id
        notes = await notes_collection.find({'user_id': user_id}).to_list(length=None)
        tasks = await tasks_collection.find({'user_id': user_id}).to_list(length=None)
        if not notes and not tasks:
            await send_split_message(update, "📝 No items to search", parse_mode="Markdown")
            return
        content = []
        for note in notes:
            content.append(f"Note ({note['timestamp'].strftime('%Y-%m-%d')}): {note['text']}")
        for task in tasks:
            content.append(f"Task ({task['timestamp'].strftime('%Y-%m-%d')}): {task['text']} (Status: {task['status']})")
        prompt = f"""Find exact matches for: "{query}"
Content:
{chr(10).join(content)}

Return only the matching items as bullet points. Each bullet point should start with 🔹. Do not include any intermediate reasoning.
"""
        response = await ollama_client.generate_response(prompt)
        if response:
            await send_split_message(update, f"🔍 *Search Results:*\n\n{response}", parse_mode="Markdown")
        else:
            await send_split_message(update, "❌ No matches found", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error searching: {e}")
        await send_split_message(update, "❌ Error during search. Please try again.", parse_mode="Markdown")

async def get_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """📊 Generate summary with bullet points."""
    try:
        user_id = update.effective_user.id
        notes = await notes_collection.find({'user_id': user_id}).to_list(length=None)
        tasks = await tasks_collection.find({'user_id': user_id}).to_list(length=None)
        if not notes and not tasks:
            await send_split_message(update, "📝 No items to summarize", parse_mode="Markdown")
            return
        content = []
        for note in sorted(notes, key=lambda x: x['timestamp'], reverse=True)[:5]:
            content.append(f"Note: {note['text']}")
        for task in sorted(tasks, key=lambda x: x['timestamp'], reverse=True)[:5]:
            content.append(f"Task: {task['text']} (Status: {task['status']})")
        prompt = f"""Summarize these items concisely.
Items:
{chr(10).join(content)}

Return only the final summary as bullet points (each starting with 🔹), including total counts.
"""
        response = await ollama_client.generate_response(prompt)
        if response:
            formatted_response = f"""📊 *Summary of Your Items:*

🔹 Total Notes: {len(notes)}
🔹 Total Tasks: {len(tasks)}

{response}

👉 Use `/list` to view all items."""
            await send_split_message(update, formatted_response, parse_mode="Markdown")
        else:
            basic_summary = f"""📊 *Basic Summary:*

🔹 Total Notes: {len(notes)}
🔹 Total Tasks: {len(tasks)}

Recent Items:
🔹 {chr(10).join(content[:3])}

👉 Use `/list` to view all items."""
            await send_split_message(update, basic_summary, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        await send_split_message(update, "❌ Error generating summary. Please try again.", parse_mode="Markdown")

async def query_general(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🤖 Handle a general-purpose query without any internal thinking."""
    try:
        if not context.args:
            await send_split_message(update, "❌ Please provide a query!\nExample: `/query What is the capital of France?`", parse_mode="Markdown")
            return
        user_query = ' '.join(context.args)
        prompt = f"""For the following input, return only the final answer as bullet points (each starting with 🔹). Do not include any intermediate reasoning.
Input: {user_query}
"""
        response = await ollama_client.generate_response(prompt)
        if response:
            await send_split_message(update, f"🤖 *Response:*\n{response}", parse_mode="Markdown")
        else:
            await send_split_message(update, "ℹ️ No response from the AI. Please try again.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        await send_split_message(update, "❌ Error processing query. Please try again.", parse_mode="Markdown")

async def summarize_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🗣️ Summarize a meeting transcript from a voice message."""
    try:
        if update.message.voice is None:
            await send_split_message(update, "❌ Please attach a voice message with your meeting transcript after using the /summarize_meeting command.", parse_mode="Markdown")
            return
        
        # Download the voice file
        file_id = update.message.voice.file_id
        voice_file = await context.bot.get_file(file_id)
        temp_filename = "temp_voice.ogg"
        await voice_file.download_to_drive(temp_filename)
        
        # Transcribe using Whisper (install via: pip install git+https://github.com/openai/whisper.git)
        import whisper
        whisper_model = whisper.load_model("base")
        result = whisper_model.transcribe(temp_filename)
        transcript = result["text"]
        os.remove(temp_filename)
        
        # Create prompt for summarization
        prompt = f"""Summarize the following meeting transcript and list follow-up action items as bullet points (each starting with 🔹). Do not include any internal thinking.
Meeting Transcript:
{transcript}
"""
        summary_response = await ollama_client.generate_response(prompt)
        if summary_response:
            await send_split_message(update, f"🗣️ *Meeting Summary:*\n\n{summary_response}", parse_mode="Markdown")
        else:
            await send_split_message(update, "❌ No summary could be generated. Please try again.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error summarizing meeting: {e}")
        await send_split_message(update, "❌ Error processing meeting summary. Please try again.", parse_mode="Markdown")

async def delete_all_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🗑️ Delete all tasks for the user."""
    try:
        user_id = update.effective_user.id
        result = await tasks_collection.delete_many({'user_id': user_id})
        await send_split_message(update, f"🗑️ Deleted {result.deleted_count} task(s).", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error deleting tasks: {e}")
        await send_split_message(update, "❌ Error deleting tasks. Please try again.", parse_mode="Markdown")

async def delete_all_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🗑️ Delete all notes for the user."""
    try:
        user_id = update.effective_user.id
        result = await notes_collection.delete_many({'user_id': user_id})
        await send_split_message(update, f"🗑️ Deleted {result.deleted_count} note(s).", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error deleting notes: {e}")
        await send_split_message(update, "❌ Error deleting notes. Please try again.", parse_mode="Markdown")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """⚠️ Handle errors in the Telegram bot."""
    logger.error(f"Error: {context.error} for update {update}")
    await send_split_message(update, "❌ An error occurred. Please try again.", parse_mode="Markdown")

def main() -> None:
    """🚀 Start the bot."""
    try:
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            logger.error("No bot token found!")
            return
        application = Application.builder().token(token).build()
        
        # Check services
        asyncio.get_event_loop().run_until_complete(check_services())

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", start))
        application.add_handler(CommandHandler("note", save_note))
        application.add_handler(CommandHandler("task", add_task))
        application.add_handler(CommandHandler("list", list_items))
        application.add_handler(CommandHandler("search", search))
        application.add_handler(CommandHandler("summary", get_summary))
        application.add_handler(CommandHandler("query", query_general))
        application.add_handler(CommandHandler("summarize_meeting", summarize_meeting))
        application.add_handler(CommandHandler("delete_tasks", delete_all_tasks))
        application.add_handler(CommandHandler("delete_notes", delete_all_notes))
        
        application.add_error_handler(error_handler)

        logger.info("🚀 Starting bot...")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

if __name__ == '__main__':
    main()
