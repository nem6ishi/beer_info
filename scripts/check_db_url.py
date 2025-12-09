
import os
from dotenv import load_dotenv

load_dotenv('.env')

if os.environ.get("DATABASE_URL"):
    print("DATABASE_URL found.")
else:
    print("DATABASE_URL NOT found.")
