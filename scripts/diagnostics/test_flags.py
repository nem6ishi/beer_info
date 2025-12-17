import os
import sys

# Mock logic to test getFlag behavior in Python (simulating JS logic)
def get_flag(location):
    if not location: return '🏳️'
    loc = location.lower()
    
    if 'japan' in loc: return '🇯🇵'
    if 'united states' in loc or 'usa' in loc or 'america' in loc: return '🇺🇸'
    if 'canada' in loc: return '🇨🇦'
    if 'united kingdom' in loc or 'uk' in loc or 'england' in loc: return '🇬🇧'
    if 'australia' in loc: return '🇦🇺'
    if 'new zealand' in loc: return '🇳🇿'
    if 'germany' in loc: return '🇩🇪'
    if 'belgium' in loc: return '🇧🇪'
    if 'france' in loc: return '🇫🇷'
    # ... (other mappings)
    return '🏳️'

def test_flags():
    test_locations = [
        "Tokyo, Japan",
        "San Diego, CA United States",
        "Brussels, Belgium",
        "Unknown Location",
        "London, UK"
    ]
    
    print("Testing Flag Mapping Logic:")
    for loc in test_locations:
        print(f"{loc} -> {get_flag(loc)}")

if __name__ == "__main__":
    test_flags()
