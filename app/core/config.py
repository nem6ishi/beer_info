import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    SCRAPER_SOLD_OUT_THRESHOLD: int = int(os.getenv("SCRAPER_SOLD_OUT_THRESHOLD", "30"))
    
    # Add other settings as needed

settings = Settings()
