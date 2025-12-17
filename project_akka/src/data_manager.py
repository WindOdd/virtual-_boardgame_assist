"""
Project Akka - Data Manager Module
Logic to load Registry and handle the 'enable_stt_injection' switch

This module handles:
1. Loading games registry from YAML
2. Managing STT keyword injection per game
3. Loading game rules from markdown files
4. Caching and hot-reloading capabilities
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import yaml


@dataclass
class GameEntry:
    """Represents a game entry from the registry."""
    id: str
    display_name: str
    rule_path: str
    keywords_path: str
    enable_stt_injection: bool = True
    metadata: Dict = field(default_factory=dict)
    
    # Cached content (loaded on demand)
    _rules_content: Optional[str] = field(default=None, repr=False)
    _keywords: Optional[List[str]] = field(default=None, repr=False)


class DataManager:
    """
    Central data management for Project Akka.
    
    Responsibilities:
    - Load and cache game registry
    - Provide game rules and STT keywords
    - Handle the enable_stt_injection switch
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize the data manager.
        
        Args:
            base_path: Root path for data files (defaults to project root)
        """
        self.base_path = base_path or Path(__file__).parent.parent
        self._games: Dict[str, GameEntry] = {}
        self._loaded = False
    
    def load_registry(self, registry_path: Optional[str] = None) -> None:
        """
        Load the games registry from YAML.
        
        Args:
            registry_path: Path to registry file (defaults to data/games_registry.yaml)
        """
        if registry_path is None:
            registry_path = self.base_path / "data" / "games_registry.yaml"
        else:
            registry_path = Path(registry_path)
        
        with open(registry_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        self._games = {}
        for game_data in data.get('games', []):
            game = GameEntry(
                id=game_data['id'],
                display_name=game_data['display_name'],
                rule_path=game_data['rule_path'],
                keywords_path=game_data['keywords_path'],
                enable_stt_injection=game_data.get('enable_stt_injection', True),
                metadata=game_data.get('metadata', {})
            )
            self._games[game.id] = game
        
        self._loaded = True
    
    def get_game(self, game_id: str) -> Optional[GameEntry]:
        """Get a game entry by ID."""
        if not self._loaded:
            self.load_registry()
        return self._games.get(game_id)
    
    def list_games(self) -> List[GameEntry]:
        """List all registered games."""
        if not self._loaded:
            self.load_registry()
        return list(self._games.values())
    
    def get_rules(self, game_id: str) -> Optional[str]:
        """
        Get the rules content for a game.
        
        Returns the markdown content of the rules file.
        """
        game = self.get_game(game_id)
        if game is None:
            return None
        
        if game._rules_content is None:
            rule_path = self.base_path / game.rule_path
            if rule_path.exists():
                with open(rule_path, 'r', encoding='utf-8') as f:
                    game._rules_content = f.read()
        
        return game._rules_content
    
    def get_stt_keywords(self, game_id: str) -> Optional[List[str]]:
        """
        Get STT keywords for a game if injection is enabled.
        
        Returns None if:
        - Game not found
        - enable_stt_injection is False
        - Keywords file doesn't exist
        """
        game = self.get_game(game_id)
        if game is None:
            return None
        
        # Check the injection switch
        if not game.enable_stt_injection:
            return None
        
        if game._keywords is None:
            keywords_path = self.base_path / game.keywords_path
            if keywords_path.exists():
                with open(keywords_path, 'r', encoding='utf-8') as f:
                    game._keywords = [
                        line.strip() 
                        for line in f.readlines() 
                        if line.strip()
                    ]
        
        return game._keywords
    
    def reload(self) -> None:
        """Force reload of the registry and clear caches."""
        self._games = {}
        self._loaded = False
        self.load_registry()


# Singleton instance for convenience
_data_manager: Optional[DataManager] = None


def get_data_manager() -> DataManager:
    """Get the global DataManager instance."""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager
