import os, re, sys, time, urllib.parse
from dotenv import load_dotenv

# Repo içinden Sentient model sınıfını görmesi için kökü path'e ekle
sys.path.append(os.path.abspath("."))

# --- Sentient model ---
try:
    from src.agent.agent_tools.model.model import Model
except Exception as e:
    Model = None
    print("⚠️ Sentient Model import edilemedi:", e)

# --- Telegram & scraping & browser ---
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from playwright.sync_api import sync_playwright

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTO_POST = os.getenv("AUTO_POST", "true").lower() == "true"
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
PROFILE_DIR = os.getenv("TWITTER_PROFILE_DIR", "./tw_profile")

TWEET_URL_RE = re.compile(r"(https?://(?:www\.)?(?:x|twitter)\.com/\w+/status/(\d+))")

# Sentient model başlat
sentient_model = None
if Model is not None:
    try:
        sentient_model = Model(os.getenv("MODEL_API_KEY"))
    except Exception as e:
        print("⚠️ Sentient Model başlatılamadı:", e)

def fetch_tweet_text(tweet_id: str):
    """
    Tweet içeriğini Playwright ile doğrudan X sayfasından çeker.
    """
    from playwright.sync_api import sync_playwright

    tweet_url = f"https://x.com/i/status/{tweet_id}"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(tweet_url, timeout=30000)
            page.wait_for_timeout(4000)  # sayfanın yüklenmesini bekle
            # tweet metnini seç
            tweet_texts = page.locator("article div[lang]").all_inner_texts()
            browser.close()

            if tweet_texts:
                print("✅ Tweet bulundu!")
                return tweet_texts[0]
            else:
                print("❌ Tweet içeriği bulunamadı.")
                return None
    except Exception as e:
        print("⚠️ Tweet çekme hatası:", e)
        return None

def generate_reply_with_sentient(tweet_text: str) -> str:
    """
    Sentient modelden kısa, tek cümlelik bir yorum üretir.
    Model çalışmazsa geçici fallback döner.
    """
    prompt = (
        "Sen kısa ve somut yorumlar üreten bir sosyal AI'sın.\n"
        "Aşağıdaki tweete TEK cümlelik, faydalı ve klişe olmayan bir yanıt üret. "
        "Emoji ve hashtag kullanma. En fazla 220 karakter. "
        "Cevabı TÜRKÇE yaz.\n\n"
        f"TWEET:\n{tweet_text.strip()}\n"
    )

    if sentient_model:
        try:
            out = sentient_model.query(prompt)  # <- Sentient'in asıl metodu
            return (out or "").strip()[:220]
        except Exception as e:
            print("⚠️ Sentient query hatası:", e)

    # Geçici fallback – yalnızca model başarısızsa
    import random
    fallbacks = [
        "Güzel içgörü. Bunu biraz daha açabilir misin?",
        "İlginç bir yaklaşım; hangi veriye dayanıyor?",
        "Detay verebilir misin? Süreç/araç/amaç kısmı merak ettim.",
        "Bunu destekleyen başka bir örnek paylaşabilir misin?",
        "Düşündürücü; pratikte nasıl uygulamayı planlıyorsun?"
    ]
    return random.choice(fallbacks)

def post_reply_via_playwright(tweet_id: str, reply_text: str):
    """
    Reply kutusuna gerçekten yazar ve Cmd/Ctrl+Enter kısayoluyla gönderir.
    Popup (Replying to...) penceresi çıkarsa kapatır.
    """
    intent_url = f"https://twitter.com/intent/tweet?in_reply_to={tweet_id}"

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            os.path.expanduser(PROFILE_DIR),
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ]
        )
        page = ctx.new_page()
        page.goto(intent_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        try:
            # Textbox'a odaklan
            box = page.locator("div[role='textbox']").first
            box.wait_for(state="visible", timeout=15000)
            box.click()
            # Var olan metni sil
            try:
                page.keyboard.press("Meta+A")
            except:
                page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")

            # Gerçek yazma simülasyonu
            page.keyboard.type(reply_text, delay=20)

            # Popup 'Done' butonu varsa kapat
            if page.locator("div[role='dialog'] button:has-text('Done')").count() > 0:
                page.locator("div[role='dialog'] button:has-text('Done')").first.click()
                page.wait_for_timeout(500)

            # Butonun aktifleşmesini bekle (metin yazıldıktan sonra)
            for _ in range(30):
                btn = page.locator("div[data-testid='tweetButtonInline'], div[data-testid='tweetButton']")
                if btn.count() > 0 and (btn.get_attribute("aria-disabled") in [None, "false"]):
                    btn.first.click()
                    print("✅ Reply butonuna tıklandı.")
                    break
                page.wait_for_timeout(200)

            # Eğer hala gönderilmediyse kısayolu dene
            page.keyboard.press("Meta+Enter")
            page.wait_for_timeout(1000)
            page.keyboard.press("Control+Enter")

            page.wait_for_timeout(4000)
            print("✅ Reply gönderme işlemi tamamlandı.")
        except Exception as e:
            print("❌ Reply gönderme hatası:", e)
        finally:
            if HEADLESS:
                ctx.close()

def handle_message(update: Update, context: CallbackContext):
    msg = update.message
    if not msg or not (msg.text or ""):
        return
    text = msg.text

    # Grup ise bot mention edilmeden çalışmasın (spam önlemek için)
    if msg.chat.type in ("group", "supergroup"):
        botname = context.bot.username or ""
        if f"@{botname}" not in text:
            return

    m = TWEET_URL_RE.search(text)
    if not m:
        return

    tweet_url, tweet_id = m.group(1), m.group(2)
    msg.reply_text("🧠 Alıyorum…")

    ttext = fetch_tweet_text(tweet_id)
    if not ttext:
        msg.reply_text("Tweet içeriğini alamadım (gizli/silinmiş olabilir).")
        return

    reply = generate_reply_with_sentient(ttext)
    if not reply:
        msg.reply_text("Cevap üretilemedi.")
        return

    if AUTO_POST:
        msg.reply_text("🚀 Gönderiyorum… (İlk seferde açılan pencereden X'e giriş yap)")
        post_reply_via_playwright(tweet_id, reply)
        msg.reply_text("Bitti gibi. X'te kontrol edebilirsin.")
    else:
        intent = f"https://twitter.com/intent/tweet?in_reply_to={tweet_id}&text={urllib.parse.quote(reply)}"
        msg.reply_text(f"Öneri:\n{reply}\n\nGöndermek için: {intent}")

def main():
    if not TELEGRAM_TOKEN:
        print("TELEGRAM_BOT_TOKEN eksik ('.env' dosyasına koy).")
        return
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_message))
    print("✅ Telegram bot hazır. Gruba ekleyip botu mention + tweet linki at.")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
