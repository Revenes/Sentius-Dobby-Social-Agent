# 🧠 Sentius Dobby — Social Agent

**Sentius Dobby** is an autonomous social agent designed to interact with social media platforms like **Twitter/X** and **Telegram**, powered by Python and Playwright automation.

> ⚙️ Built and maintained by [@Revenes](https://github.com/Revenes)

---

## 🚀 Features

- Auto-fetches and analyzes latest posts from selected Twitter accounts  
- Smart Telegram auto-reply system  
- Configurable via environment variables  
- Built with Playwright for stable headless browser automation  
- Modular structure under `/src` for easy expansion  

---

## 🛠️ Requirements

- **Python 3.12.x** (⚠️ Do not use 3.13 – currently unstable for Playwright)
- **pip** & **venv**
- **Playwright** dependencies

---

## ⚙️ Installation

Clone the repo and install dependencies:

```bash
git clone https://github.com/Revenes/Sentius-Dobby-Social-Agent.git
cd Sentius-Dobby-Social-Agent

# Create virtual environment (use Python 3.12)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Chromium for Playwright
python3 -m playwright install chromium


⸻

▶️ Running the Bot

Run the Telegram auto-reply agent:

python3 telegram_auto_reply_bot.py

The bot will:
	•	Launch a persistent browser session
	•	Monitor specific accounts or messages
	•	Reply or post automatically based on configured prompts

⸻

📁 Folder Structure

Sentient-Social-Agent/
│
├── src/                       # Core source code and modules
├── telegram_auto_reply_bot.py  # Main executable
├── requirements.txt            # Dependencies
├── README.md                   # Documentation
├── LICENSE
├── banner.png                  # Branding asset
├── state.json                  # Local runtime state (ignored in Git)
├── venv/                       # Virtual environment (ignored)
└── __pycache__/                # Python cache (ignored)


⸻

🚫 Ignored Files

The following are not uploaded to GitHub:

venv/
__pycache__/
state.json
*.log
.DS_Store

Add them to your .gitignore if not already:

echo "venv/
__pycache__/
state.json
*.log
.DS_Store" > .gitignore


⸻

💬 Author

Revenes — building the next generation of social AI systems.
Follow on Twitter or GitHub.

⸻

🧩 License

This project is licensed under the MIT License — see LICENSE for details.

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.pyd

# Virtual env
venv/

# macOS
.DS_Store

# Logs & state
*.log
state.json

# Playwright artifacts (optional)
playwright-report/
test-results/