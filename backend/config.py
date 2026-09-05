import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "false").lower() == "true"

if not GEMINI_API_KEY and not USE_MOCK_LLM:
    raise RuntimeError(
        "GEMINI_API_KEY not found. Make sure you created a .env file "
        "in the project root with GEMINI_API_KEY=your_key_here"
    )

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")
