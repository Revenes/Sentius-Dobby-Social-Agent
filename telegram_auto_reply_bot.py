import os, re, sys, urllib.parse, random, asyncio, time
from dotenv import load_dotenv
from langdetect import detect
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from playwright.async_api import async_playwright, Error as PlaywrightError

# --- PATH ayarları ---
sys.path.append(os.path.abspath("."))

# --- Sentient Model import ---
try:
    from src.agent.agent_tools.model.model import Model
except Exception as e:
    Model = None
    print("⚠️ Sentient Model import failed:", e)

# --- .env ayarları ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTO_POST = os.getenv("AUTO_POST", "true").lower() == "true"
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
PROFILE_DIR = os.getenv("TWITTER_PROFILE_DIR", "./tw_profile")

TWEET_URL_RE = re.compile(r"(https?://(?:www\.)?(?:x|twitter)\.com/\w+/status/(\d+))")

sentient_model = None
if Model is not None:
    try:
        sentient_model = Model(os.getenv("MODEL_API_KEY"))
    except Exception as e:
        print("⚠️ Sentient Model initialization failed:", e)


# --- Güvenli Chromium başlatıcı ---
async def safe_launch(pw, retries=3, delay=2):
    """MacOS Chromium crash hatalarına karşı güvenli başlatma."""
    user_data_dir = os.path.expanduser(PROFILE_DIR)
    for attempt in range(1, retries + 1):
        try:
            browser = await pw.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=HEADLESS,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--use-gl=swiftshader",
                    "--disable-software-rasterizer",
                ],
            )
            return browser
        except PlaywrightError as e:
            print(f"⚠️ Chromium launch failed (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
            else:
                raise


# --- Tweet metnini çek (Persistent login + retry) ---
async def fetch_tweet_text(tweet_id: str):
    tweet_url = f"https://x.com/i/status/{tweet_id}"
    try:
        async with async_playwright() as pw:
            browser = await safe_launch(pw)
            page = await browser.new_page()

            print(f"🌐 Opening tweet: {tweet_url}")
            await page.goto(tweet_url, timeout=60000)
            await page.wait_for_timeout(6000)

            tweet_texts = await page.locator("article div[lang]").all_inner_texts()
            await browser.close()

            if tweet_texts:
                print("✅ Tweet text fetched.")
                return tweet_texts[0]
            else:
                print("⚠️ Could not find tweet text.")
                return None
    except Exception as e:
        print("⚠️ Tweet fetch error:", e)
        return None


# --- Cevap üret ---
def generate_reply_with_sentient(tweet_text: str) -> str:
    try:
        lang = detect(tweet_text)
    except:
        lang = "en"

    persona = (
        "You are Dobby — a witty, confident but respectful community member created by Revenes. "
        "Your humor is subtle, intelligent and slightly sarcastic, never rude. "
        "You never use profanity, slang or offensive language. "
        "You answer with calm confidence, thoughtful irony, and a clean tone. "
        "You sound like a chill person who’s been online for years and knows when to be clever or insightful. "
        "Your replies are concise (max 200 chars), human-like, and shareable."
    )

    if lang.startswith("tr"):
        prompt = (
            f"{persona}\n\n"
            "Aşağıdaki tweete kısa, zeki ve doğal bir yanıt yaz. "
            "Tonun hafif alaycı, samimi ve saygılı olsun. "
            "Küfür, argo, aşırı şaka ya da küçümseme yok. "
            "Cevabı TÜRKÇE yaz. Maksimum 220 karakter.\n\n"
            f"TWEET:\n{tweet_text.strip()}\n"
        )
    else:
        prompt = (
            f"{persona}\n\n"
            "Write a short, witty, and natural reply to the tweet below. "
            "Keep it subtly sarcastic, never rude or offensive. "
            "Respond in ENGLISH. Max 220 characters.\n\n"
            f"TWEET:\n{tweet_text.strip()}\n"
        )

    if sentient_model:
        try:
            out = sentient_model.query(prompt)
            reply = (out or "").strip()
            if (reply.startswith('"') and reply.endswith('"')) or (reply.startswith("'") and reply.endswith("'")):
                reply = reply[1:-1].strip()
            return reply[:220]
        except Exception as e:
            print("⚠️ Sentient query error:", e)

    fallbacks_tr = [
        "İronik bir tespit, hoşuma gitti.",
        "Kesinlikle düşünmeye değer bir yorum.",
        "Sade ama zekice yazılmış.",
        "Kısa ama etkili bir düşünce.",
        "Güzel bakış açısı, beğendim."
    ]
    fallbacks_en = [
        "Smart take, I like it.",
        "Short but clever.",
        "That’s actually a good point.",
        "Simple, yet on point.",
        "I see what you did there."
    ]
    return random.choice(fallbacks_tr if lang.startswith("tr") else fallbacks_en)


# --- Tweet'e yanıt gönder ---
async def post_reply_via_playwright(tweet_id: str, reply_text: str):
    from playwright.sync_api import sync_playwright
    intent_url = f"https://twitter.com/intent/tweet?in_reply_to={tweet_id}"

    def _post():
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                os.path.expanduser(PROFILE_DIR),
                headless=HEADLESS,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--use-gl=swiftshader",
                    "--disable-software-rasterizer",
                ],
            )
            page = ctx.new_page()
            page.goto(intent_url, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            try:
                box = page.locator("div[role='textbox']").first
                box.wait_for(state="visible", timeout=15000)
                box.click()
                try:
                    page.keyboard.press("Meta+A")
                except:
                    page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(reply_text, delay=20)

                for _ in range(30):
                    btn = page.locator("div[data-testid='tweetButtonInline'], div[data-testid='tweetButton']")
                    if btn.count() > 0 and (btn.get_attribute("aria-disabled") in [None, "false"]):
                        btn.first.click()
                        print("✅ Reply button clicked.")
                        break
                    page.wait_for_timeout(200)

                page.keyboard.press("Meta+Enter")
                page.wait_for_timeout(1000)
                page.keyboard.press("Control+Enter")
                page.wait_for_timeout(4000)
                print("✅ Reply successfully sent.")
            except Exception as e:
                print("⚠️ Reply send error:", e)
            finally:
                if HEADLESS:
                    ctx.close()

    await asyncio.to_thread(_post)


# --- Telegram mesaj işleyici ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    text = msg.text.strip()

    if msg.chat.type in ("group", "supergroup"):
        botname = context.bot.username or ""
        if f"@{botname}" not in text:
            return

    tweet_matches = TWEET_URL_RE.findall(text)
    if not tweet_matches:
        return

    await msg.reply_text(f"🔍 {len(tweet_matches)} tweet bulundu. İşlem başlatılıyor...")

    for i, match in enumerate(tweet_matches, start=1):
        tweet_url, tweet_id = match
        await msg.reply_text(f"📖 [{i}/{len(tweet_matches)}] Tweet alınıyor...")

        ttext = await fetch_tweet_text(tweet_id)
        if not ttext:
            await msg.reply_text(f"⚠️ [{i}] Tweet alınamadı (silinmiş veya gizli olabilir).")
            continue

        reply = generate_reply_with_sentient(ttext)
        if not reply:
            await msg.reply_text(f"⚠️ [{i}] Cevap üretilemedi.")
            continue

        if AUTO_POST:
            await msg.reply_text(f"💬 [{i}] Yanıt gönderiliyor...")
            await post_reply_via_playwright(tweet_id, reply)
            await msg.reply_text(f"✅ [{i}] Yanıt gönderildi:\n{reply}")
        else:
            intent = f"https://twitter.com/intent/tweet?in_reply_to={tweet_id}&text={urllib.parse.quote(reply)}"
            await msg.reply_text(f"💡 [{i}] Önerilen yanıt:\n{reply}\n\nElle paylaş: {intent}")

    await msg.reply_text("🎯 Tüm tweetler işlendi.")


# --- Ana fonksiyon ---
def main():
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN missing (add it to '.env').")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Dobby is online. Mention @Sentius_Dobby_Bot with a tweet link.")
    app.run_polling()


if __name__ == "__main__":
    main()
