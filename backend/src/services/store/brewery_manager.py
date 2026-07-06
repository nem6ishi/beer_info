import os
import re
from typing import List, Dict, Optional, Any
from backend.src.core.db import get_supabase_client

class BreweryManager:
    """
    Manages brewery database in Supabase.
    Provides brewery lookup and matching functionality.
    """
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.breweries: List[Dict] = []
        self.brewery_index: Dict[str, Dict] = {}
        self.load_breweries()
    
    def load_breweries(self) -> None:
        """Load brewery database from Supabase."""
        try:
            response = self.supabase.table('breweries').select('*').limit(2000).execute()
            self.breweries = response.data
            self._build_index()
            print(f"[BreweryManager] Loaded {len(self.breweries)} breweries from Supabase")
        except Exception as e:
            print(f"[BreweryManager] Error loading breweries: {e}")
            self.breweries = []
    

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
    

    def _generate_aliases(self, name_en: Optional[str], name_jp: Optional[str]) -> List[str]:
        """Generate common aliases for a brewery name."""
        aliases = []
        
        # Stop words that should NEVER be an alias on their own
        STOP_WORDS = {
            'black', 'white', 'red', 'blue', 'green', 'yellow', 'gold', 'silver',
            'west', 'east', 'north', 'south', 'central',
            'company', 'co.', 'corp.', 'ltd.', 'inc.',
            'the', 'a', 'an', 'my', 'our', 'your',
            'new', 'old', 'big', 'small', 'great', 'best',
            'beer', 'brewery', 'brewing', 'craft', 'ale', 'lager', 'ipa',
            'top', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'triple',
            'el', 'la', 'le', 'les', 'de', 'du', 'des', 'van', 'von',
            'st.', 'saint', 'mt.', 'mount'
        }
        
        if name_en:
            base_name = name_en
            for suffix in [' Brewing', ' Brewery', ' Beer', ' Co.', ' Company']:
                if base_name.endswith(suffix):
                    base_name = base_name[:-len(suffix)].strip()
                    aliases.append(base_name)
            
            words = base_name.split()
            if len(words) > 1:
                potential_alias = words[0]
                # Filter out stop words and very short aliases
                if potential_alias.lower() not in STOP_WORDS and len(potential_alias) > 2:
                    aliases.append(potential_alias)
        
        if name_jp:
            aliases.append(name_jp)
        
        return list(set([a for a in aliases if a]))
    
    def find_breweries_in_text(self, text: str) -> List[Dict]:
        """Search for all known breweries in product name."""
        if not text:
            return []
        
        text_lower = text.lower()
        found_breweries = []
        found_keys = set()
        
        # Sort keys by length descending to catch longer matches first (e.g. "West Coast Brewing" before "West Coast")
        sorted_keys = sorted(self.brewery_index.keys(), key=len, reverse=True)
        
        for key in sorted_keys:
            if key in text_lower:
                brewery = self.brewery_index[key]
                # Avoid adding same brewery multiple times via different aliases
                if brewery['name_en'] not in found_keys:
                    found_breweries.append(brewery)
                    found_keys.add(brewery['name_en'])
        
        return found_breweries

    def find_brewery_in_text(self, text: str) -> Optional[Dict]:
        """Legacy method: returns the first found brewery."""
        breweries = self.find_breweries_in_text(text)
        return breweries[0] if breweries else None
    
    def learn_brewery_alias(
        self,
        brewery_name_en: Optional[str] = None,
        new_alias: Optional[str] = None,
        untappd_url: Optional[str] = None,
    ) -> bool:
        """
        Self-Healing Dictionary: Automatically learn and persist a new alias or Japanese name for a known brewery.
        
        Returns:
            True if a new alias was learned and persisted to DB, False otherwise.
        """
        if not new_alias or not (brewery_name_en or untappd_url):
            return False
            
        new_alias = new_alias.strip()
        if len(new_alias) <= 1:
            return False
            
        # Ignore common generic words / suffixes
        stop_words = {
            'beer', 'brewery', 'brewing', 'craft', 'ale', 'lager', 'ipa', 'co', 'inc', 'ltd',
            'company', 'brewing co', 'brewing company', 'beer co', 'beer company'
        }
        if new_alias.lower() in stop_words:
            return False

        target_brewery: Optional[Dict] = None
        
        if untappd_url:
            for b in self.breweries:
                if b.get('untappd_url') == untappd_url:
                    target_brewery = b
                    break
                    
        if not target_brewery and brewery_name_en:
            target_brewery = self.brewery_index.get(brewery_name_en.lower())
            
        if not target_brewery or not target_brewery.get('id'):
            return False
            
        # Check if already known
        existing_en = target_brewery.get('name_en') or ''
        existing_jp = target_brewery.get('name_jp') or ''
        current_aliases = list(target_brewery.get('aliases') or [])
        
        alias_lower = new_alias.lower()
        if alias_lower == existing_en.lower() or alias_lower == existing_jp.lower():
            return False
        if any(alias_lower == a.lower() for a in current_aliases):
            return False
            
        # Prepare updates
        payload: Dict[str, Any] = {}
        updated_jp = False
        
        # If it's Japanese characters and name_jp is empty, populate name_jp
        is_japanese = bool(re.search(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]', new_alias))
        if is_japanese and not existing_jp:
            target_brewery['name_jp'] = new_alias
            payload['name_jp'] = new_alias
            updated_jp = True
            
        if not updated_jp or new_alias not in current_aliases:
            current_aliases.append(new_alias)
            target_brewery['aliases'] = current_aliases
            payload['aliases'] = current_aliases
            
        if not payload:
            return False
            
        try:
            self.supabase.table('breweries').update(payload).eq('id', target_brewery['id']).execute()
            self.brewery_index[alias_lower] = target_brewery
            print(f"[BreweryManager] 📈 Self-Healing Dict: Learned new alias '{new_alias}' for brewery '{target_brewery.get('name_en')}'")
            return True
        except Exception as e:
            print(f"[BreweryManager] Error persisting new alias to DB: {e}")
            return False

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
