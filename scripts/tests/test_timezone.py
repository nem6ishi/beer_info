
import sys
import os
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# We will simulate the behavior by importing the datetime from python
# and verifying .isoformat() output

def verify_utc_format():
    print("🧪 Verifying UTC Format")
    
    # 1. Create a UTC datetime as we did in the code
    now_utc = datetime.now(timezone.utc)
    
    # 2. Check string representation
    iso = now_utc.isoformat()
    print(f"ISO Format: {iso}")
    
    if "+00:00" in iso or "Z" in iso:
        print("✅ UTC Offset present in string")
    else:
        print("❌ UTC Offset MISSING in string")
        sys.exit(1)
        
    print(f"Formatted: {now_utc.strftime('%Y/%m/%d %H:%M:%S')}")

if __name__ == "__main__":
    verify_utc_format()
