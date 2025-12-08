import os
from typing import List, Dict, Optional
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)


class BreweryManager:
    """
    Manages brewery database in Supabase.
    Provides brewery lookup and matching functionality.
    """
    
    def __init__(self):
        supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.breweries: List[Dict] = []
        self.brewery_index: Dict[str, Dict] = {}
        self.load_breweries()
    
    def load_breweries(self) -> None:
        """Load brewery database from Supabase."""
        try:
            response = self.supabase.table('breweries').select('*').execute()
            self.breweries = response.data
            self._build_index()
            print(f"[BreweryManager] Loaded {len(self.breweries)} breweries from Supabase")
        except Exception as e:
            print(f"[BreweryManager] Error loading breweries: {e}")
            self.breweries = []
    
    def save_breweries(self) -> None:
        """Save is now handled per-operation via upsert. This is a no-op for compatibility."""
        pass
    
    def _build_index(self) -> None:
        """Build index for fast brewery lookup."""
        self.brewery_index = {}
        for brewery in self.breweries:
            if brewery.get('name_en'):
                self.brewery_index[brewery['name_en'].lower()] = brewery
            if brewery.get('name_jp'):
                self.brewery_index[brewery['name_jp'].lower()] = brewery
            for alias in (brewery.get('aliases') or []):
                self.brewery_index[alias.lower()] = brewery
    
    def extract_breweries_from_beers(self, beers: List[Dict]) -> int:
        """
        Extract unique breweries from beer data (Untappd field).
        Upserts to Supabase.
        Returns number of new breweries added.
        """
        existing_names = {b.get('name_en', '').lower() for b in self.breweries}
        new_breweries = []
        
        for beer in beers:
            untappd_brewery = beer.get('untappd_brewery_name')
            if not untappd_brewery:
                continue
            
            if untappd_brewery.lower() in existing_names:
                continue
            
            brewery_name_jp = beer.get('brewery_name_jp')
            aliases = self._generate_aliases(untappd_brewery, brewery_name_jp)
            
            new_brewery = {
                "name_en": untappd_brewery,
                "name_jp": brewery_name_jp,
                "aliases": aliases,
            }
            
            new_breweries.append(new_brewery)
            existing_names.add(untappd_brewery.lower())
        
        # Upsert to Supabase
        if new_breweries:
            try:
                self.supabase.table('breweries').upsert(
                    new_breweries, 
                    on_conflict='name_en'
                ).execute()
                print(f"[BreweryManager] Upserted {len(new_breweries)} breweries to Supabase")
                
                # Reload to get IDs
                self.load_breweries()
            except Exception as e:
                print(f"[BreweryManager] Error upserting breweries: {e}")
                return 0
        
        return len(new_breweries)
    
    def _generate_aliases(self, name_en: Optional[str], name_jp: Optional[str]) -> List[str]:
        """Generate common aliases for a brewery name."""
        aliases = []
        
        if name_en:
            base_name = name_en
            for suffix in [' Brewing', ' Brewery', ' Beer', ' Co.', ' Company']:
                if base_name.endswith(suffix):
                    base_name = base_name[:-len(suffix)].strip()
                    aliases.append(base_name)
            
            words = base_name.split()
            if len(words) > 1:
                aliases.append(words[0])
        
        if name_jp:
            aliases.append(name_jp)
        
        return list(set([a for a in aliases if a]))
    
    def find_brewery_in_text(self, text: str) -> Optional[Dict]:
        """Search for known brewery in product name."""
        if not text:
            return None
        
        text_lower = text.lower()
        
        for key, brewery in self.brewery_index.items():
            if key in text_lower:
                return brewery
        
        return None
    
    def add_brewery(self, name_en: str, name_jp: Optional[str] = None) -> None:
        """Manually add a brewery to the database."""
        if name_en.lower() in {b.get('name_en', '').lower() for b in self.breweries}:
            print(f"[BreweryManager] Brewery '{name_en}' already exists")
            return
        
        aliases = self._generate_aliases(name_en, name_jp)
        
        new_brewery = {
            "name_en": name_en,
            "name_jp": name_jp,
            "aliases": aliases,
        }
        
        try:
            self.supabase.table('breweries').insert(new_brewery).execute()
            self.load_breweries()
            print(f"[BreweryManager] Added brewery: {name_en}")
        except Exception as e:
            print(f"[BreweryManager] Error adding brewery: {e}")
    
    def get_stats(self) -> Dict:
        """Get statistics about brewery database."""
        total = len(self.breweries)
        with_jp_names = sum(1 for b in self.breweries if b.get('name_jp'))
        
        return {
            "total_breweries": total,
            "with_japanese_names": with_jp_names,
        }


if __name__ == "__main__":
    manager = BreweryManager()
    stats = manager.get_stats()
    print(f"Brewery Database Stats:")
    print(f"  Total breweries: {stats['total_breweries']}")
    print(f"  With Japanese names: {stats['with_japanese_names']}")
