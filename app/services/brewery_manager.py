import json
import os
from typing import List, Dict, Optional, Set
from datetime import datetime
from pathlib import Path

class BreweryManager:
    """
    Manages brewery database extracted from Untappd data.
    Provides brewery lookup and matching functionality.
    """
    
    def __init__(self, db_path: str = "data/breweries.json"):
        self.db_path = db_path
        self.breweries: List[Dict] = []
        self.brewery_index: Dict[str, Dict] = {}  # For fast lookup
        self.load_breweries()
    
    def load_breweries(self) -> None:
        """Load brewery database from JSON file."""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.breweries = data.get('breweries', [])
                    self._build_index()
                print(f"[BreweryManager] Loaded {len(self.breweries)} breweries from {self.db_path}")
            except Exception as e:
                print(f"[BreweryManager] Error loading breweries: {e}")
                self.breweries = []
        else:
            print(f"[BreweryManager] No brewery database found. Creating new one.")
            self.breweries = []
    
    def save_breweries(self) -> None:
        """Save brewery database to JSON file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            data = {
                "breweries": self.breweries,
                "last_updated": datetime.now().isoformat(),
                "total_count": len(self.breweries)
            }
            
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"[BreweryManager] Saved {len(self.breweries)} breweries to {self.db_path}")
        except Exception as e:
            print(f"[BreweryManager] Error saving breweries: {e}")
    
    def _build_index(self) -> None:
        """Build index for fast brewery lookup."""
        self.brewery_index = {}
        for brewery in self.breweries:
            # Index by English name
            if brewery.get('name_en'):
                key = brewery['name_en'].lower()
                self.brewery_index[key] = brewery
            
            # Index by Japanese name
            if brewery.get('name_jp'):
                key = brewery['name_jp'].lower()
                self.brewery_index[key] = brewery
            
            # Index by aliases
            for alias in brewery.get('aliases', []):
                key = alias.lower()
                self.brewery_index[key] = brewery
    
    def extract_breweries_from_beers(self, beers: List[Dict]) -> int:
        """
        Extract unique breweries from beer data (Untappd field).
        Returns number of new breweries added.
        """
        existing_names = {b.get('name_en', '').lower() for b in self.breweries}
        new_count = 0
        
        for beer in beers:
            untappd_brewery = beer.get('untappd_brewery_name')
            if not untappd_brewery:
                continue
            
            # Check if brewery already exists
            if untappd_brewery.lower() in existing_names:
                # Update beer count
                for brewery in self.breweries:
                    if brewery.get('name_en', '').lower() == untappd_brewery.lower():
                        brewery['beer_count'] = brewery.get('beer_count', 0) + 1
                        break
                continue
            
            # Extract Japanese name from Gemini data if available
            brewery_name_jp = beer.get('brewery_name_jp')
            
            # Create aliases (common variations)
            aliases = self._generate_aliases(untappd_brewery, brewery_name_jp)
            
            # Add new brewery
            new_brewery = {
                "name_en": untappd_brewery,
                "name_jp": brewery_name_jp,
                "aliases": aliases,
                "source": "untappd",
                "first_seen": datetime.now().isoformat(),
                "beer_count": 1
            }
            
            self.breweries.append(new_brewery)
            existing_names.add(untappd_brewery.lower())
            new_count += 1
        
        # Rebuild index after adding new breweries
        self._build_index()
        
        return new_count
    
    def _generate_aliases(self, name_en: Optional[str], name_jp: Optional[str]) -> List[str]:
        """Generate common aliases for a brewery name."""
        aliases = []
        
        if name_en:
            # Remove common suffixes
            base_name = name_en
            for suffix in [' Brewing', ' Brewery', ' Beer', ' Co.', ' Company']:
                if base_name.endswith(suffix):
                    base_name = base_name[:-len(suffix)].strip()
                    aliases.append(base_name)
            
            # Add first word if multi-word
            words = base_name.split()
            if len(words) > 1:
                aliases.append(words[0])
        
        if name_jp:
            aliases.append(name_jp)
        
        # Remove duplicates and empty strings
        return list(set([a for a in aliases if a]))
    
    def find_brewery_in_text(self, text: str) -> Optional[Dict]:
        """
        Search for known brewery in product name.
        Returns brewery dict if found, None otherwise.
        """
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Try exact match first
        for key, brewery in self.brewery_index.items():
            if key in text_lower:
                return brewery
        
        return None
    
    def add_brewery(self, name_en: str, name_jp: Optional[str] = None) -> None:
        """Manually add a brewery to the database."""
        # Check if already exists
        if name_en.lower() in {b.get('name_en', '').lower() for b in self.breweries}:
            print(f"[BreweryManager] Brewery '{name_en}' already exists")
            return
        
        aliases = self._generate_aliases(name_en, name_jp)
        
        new_brewery = {
            "name_en": name_en,
            "name_jp": name_jp,
            "aliases": aliases,
            "source": "manual",
            "first_seen": datetime.now().isoformat(),
            "beer_count": 0
        }
        
        self.breweries.append(new_brewery)
        self._build_index()
        print(f"[BreweryManager] Added brewery: {name_en}")
    
    def get_brewery_stats(self) -> Dict:
        """Get statistics about brewery database."""
        total = len(self.breweries)
        with_jp_names = sum(1 for b in self.breweries if b.get('name_jp'))
        total_beers = sum(b.get('beer_count', 0) for b in self.breweries)
        
        return {
            "total_breweries": total,
            "with_japanese_names": with_jp_names,
            "total_beers_tracked": total_beers,
            "avg_beers_per_brewery": total_beers / total if total > 0 else 0
        }

if __name__ == "__main__":
    # Test the brewery manager
    manager = BreweryManager()
    
    # Load sample beers
    with open('data/beers.json', 'r', encoding='utf-8') as f:
        beers = json.load(f)
    
    # Extract breweries
    new_count = manager.extract_breweries_from_beers(beers)
    print(f"\nExtracted {new_count} new breweries")
    
    # Show stats
    stats = manager.get_brewery_stats()
    print(f"\nBrewery Database Stats:")
    print(f"  Total breweries: {stats['total_breweries']}")
    print(f"  With Japanese names: {stats['with_japanese_names']}")
    print(f"  Total beers tracked: {stats['total_beers_tracked']}")
    print(f"  Avg beers per brewery: {stats['avg_beers_per_brewery']:.1f}")
    
    # Save
    manager.save_breweries()
    
    # Test search
    test_names = [
        "ティーネイジ ピグメンツ / Teenage Pigments",
        "プライベートプレス ライフイズラウンド / Private Press Life is Round",
        "サンテアデアリアス 12 / Sante Adairius Rustic Ales"
    ]
    
    print("\nBrewery Detection Test:")
    for name in test_names:
        brewery = manager.find_brewery_in_text(name)
        if brewery:
            print(f"  ✓ '{name}' → {brewery['name_en']}")
        else:
            print(f"  ✗ '{name}' → Not found")
