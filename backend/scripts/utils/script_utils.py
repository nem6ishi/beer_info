import os
import sys
import logging
from dotenv import load_dotenv
from supabase import create_client

def load_env_robustly():
    """Attempts to load .env from various locations."""
    # Current dir
    if os.path.exists('.env'):
        load_dotenv('.env')
        return

    # Parent dir
    if os.path.exists('../.env'):
        load_dotenv('../.env')
        return
        
    # Relative to script file (if caller calls this, __file__ might be ambiguous if this is imported)
    # Better to look up from this file's position: scripts/utils/script_utils.py -> root
    
    current_file_dir = os.path.dirname(os.path.abspath(__file__)) # scripts/utils
    scripts_dir = os.path.dirname(current_file_dir) # scripts
    root_dir = os.path.dirname(scripts_dir) # root
    
    env_path = os.path.join(root_dir, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        # Last resort fallback if run from root
        pass

def setup_script(name: str):
    """
    Sets up logging and supabase client.
    Returns (supabase, logger).
    """
    # 1. Logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    logger = logging.getLogger(name)
    
    # 2. Env
    load_env_robustly()
    
    # 3. Supabase
    url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not url or not key:
        logger.error("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        sys.exit(1)
        
    supabase = create_client(url, key)
    
    return supabase, logger
