
import asyncio
from app.services.gemini_extractor import GeminiExtractor

async def verify_priority():
    print("🧪 Verifying GeminiExtractor Multi-Model Priority")
    extractor = GeminiExtractor()
    
    # Check configured models
    print("\n📋 Configured Models:")
    for i, m in enumerate(extractor.models):
        print(f"  {i+1}. {m['id']} (JSON Mode: {m['json_mode']})")
    
    # Test Extraction (should attempt Gemma 3 first)
    print("\n🚀 Testing Extraction...")
    result = await extractor.extract_info("Test Product / Test Brewery")
    # Note: Success depends on API availability, but logs will show which model was called.
    
    print("\n✅ Result:", result)

if __name__ == "__main__":
    asyncio.run(verify_priority())
