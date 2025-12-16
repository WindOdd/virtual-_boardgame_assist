import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
import yaml

logger = logging.getLogger(__name__)

class ConfigLoader:
    def __init__(self, config_file: Union[str, Path]):
        self.config_file = Path(config_file)
        self.config = None

    def load(self) -> Dict[str, Any]:
        if not self.config_file.exists():
            raise FileNotFoundError(f"Config not found: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            if self.config_file.suffix in ['.yaml', '.yml']:
                self.config = yaml.safe_load(f)
            else:
                self.config = json.load(f)
        return self.config

class PromptLoader:
    def __init__(self, prompts_dir: Union[str, Path]):
        self.prompts_dir = Path(prompts_dir)
        self.cache = {}

    def load(self, prompt_name: str) -> str:
        if prompt_name in self.cache: return self.cache[prompt_name]
        
        fpath = self.prompts_dir / f"{prompt_name}.txt"
        if not fpath.exists(): raise FileNotFoundError(f"Prompt not found: {prompt_name}")
        
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        self.cache[prompt_name] = content
        return content

    def format(self, prompt_name: str, **kwargs) -> str:
        template = self.load(prompt_name)
        return template.format(**kwargs)
