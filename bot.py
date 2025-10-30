import os
import requests
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Config from Replit Secrets (or environment variables)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    raise SystemExit("Set TELEGRAM_BOT_TOKEN and GEMINI_API_KEY environment variables")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_PROMPT_TEMPLATE = """Identify and explain the core theses and insights from this video.

Audience: Write for a crypto-native audience. Use our jargon (e.g., "Fed," "JPOW," "bps," "QT," "TradFi," "liquidity," "FUD," "counterparty risk," etc.).

Format: Use a simple list of standalone bullet points. Don't use two-part bullets.

Specificity/Hedging: Be extremely specific. Do not use hedging language (e.g., avoid words like "likely," "seems," "may," or "suggests"). State facts and conclusions directly. Include specific numbers or figures mentioned in the video (e.g., 25 bps, 76 million, six basis points) where possible.

Style: Speak directly to me in the second person. Do not use timestamps. Do not say "the video says" or "the speaker argues." Just state the key points as facts, as if you are explaining the situation to me yourself.

Summarize this YouTube video: {youtube_url}
"""

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"

def call_gemini(youtube_url: str) -> str:
    prompt = GEMINI_PROMPT_TEMPLATE.format(youtube_url=youtube_url)
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {"Content-Type": "application/json"}
    response = requests.post(f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    try:
        return data['candidates'][0]['content']['parts'][0]['text']
    except Exception:
        logger.exception("Unexpected Gemini response structure")
        return "Sorry, something went wrong processing the summary."

def extract_youtube_url(text: str) -> str | None:
    text = text.strip()
    for token in text.split():
        if "youtube.com" in token or "youtu.be" in token:
            return token
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    youtube_url = extract_youtube_url(update.message.text)
    if not youtube_url:
        return
    logger.info("Received URL in chat %s: %s", update.message.chat_id, youtube_url)
    ack = await update.message.reply_text("Got the link — fetching summary from Gemini...")
    try:
        summary = call_gemini(youtube_url)
        max_len = 4000
        if len(summary) <= max_len:
            await update.message.reply_text(summary)
        else:
            for i in range(0, len(summary), max_len):
                await update.message.reply_text(summary[i:i+max_len])
    except requests.exceptions.RequestException:
        logger.exception("API error")
        await update.message.reply_text("Error: failed to contact Gemini API.")
    finally:
        try:
            await ack.delete()
        except Exception:
            pass

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()

