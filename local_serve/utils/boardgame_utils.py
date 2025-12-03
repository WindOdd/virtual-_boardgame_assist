"""
桌遊助手共用工具庫
Boardgame Assistant Utils

適用於：
- Local Server (Jetson Orin Nano - Qwen3)
- Cloud Service (Gemini RAG)

版本：v1.0.0
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


# ==================== 通用配置載入器 ====================

class ConfigLoader:
    """
    通用配置載入器
    支援 JSON 和 YAML 格式
    """
    
    def __init__(self, config_file: Union[str, Path]):
        """
        初始化
        
        Args:
            config_file: 配置檔路徑（支援 .json 或 .yaml）
        """
        self.config_file = Path(config_file)
        self.config: Optional[Dict[str, Any]] = None
        self._format = self._detect_format()
    
    def _detect_format(self) -> str:
        """偵測配置檔格式"""
        suffix = self.config_file.suffix.lower()
        if suffix == '.json':
            return 'json'
        elif suffix in ['.yaml', '.yml']:
            return 'yaml'
        else:
            raise ValueError(f"不支援的配置檔格式: {suffix}")
    
    def load(self) -> Dict[str, Any]:
        """
        載入配置檔
        
        Returns:
            配置字典
        """
        if not self.config_file.exists():
            raise FileNotFoundError(f"配置檔不存在: {self.config_file}")
        
        try:
            if self._format == 'json':
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:  # yaml
                import yaml
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f)
            
            logger.info(f"📄 載入配置: {self.config_file.name}")
            return self.config
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON 格式錯誤: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 載入配置失敗: {e}")
            raise
    
    def reload(self) -> Dict[str, Any]:
        """
        重新載入配置（開發時使用）
        
        Returns:
            配置字典
        """
        logger.info(f"🔄 重新載入配置: {self.config_file.name}")
        self.config = None
        return self.load()
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        取得配置值（支援點號分隔的巢狀鍵）
        
        Args:
            key: 配置鍵，例如 "generation_config.temperature"
            default: 預設值
            
        Returns:
            配置值
        """
        if self.config is None:
            self.load()
        
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        設定配置值（僅記憶體，不寫入檔案）
        
        Args:
            key: 配置鍵
            value: 配置值
        """
        if self.config is None:
            self.load()
        
        keys = key.split('.')
        target = self.config
        
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        
        target[keys[-1]] = value
    
    def save(self):
        """儲存配置到檔案"""
        if self.config is None:
            raise ValueError("尚未載入配置")
        
        try:
            if self._format == 'json':
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, ensure_ascii=False, indent=2)
            else:  # yaml
                import yaml
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
            
            logger.info(f"💾 儲存配置: {self.config_file.name}")
            
        except Exception as e:
            logger.error(f"❌ 儲存配置失敗: {e}")
            raise


# ==================== Prompt 載入器 ====================

class PromptLoader:
    """
    Prompt 模板載入器
    支援熱重載
    """
    
    def __init__(self, prompts_dir: Union[str, Path]):
        """
        初始化
        
        Args:
            prompts_dir: Prompt 模板目錄
        """
        self.prompts_dir = Path(prompts_dir)
        self.cache: Dict[str, str] = {}
        
        if not self.prompts_dir.exists():
            logger.warning(f"⚠️ Prompt 目錄不存在: {self.prompts_dir}")
            self.prompts_dir.mkdir(parents=True, exist_ok=True)
    
    def load(self, prompt_name: str, use_cache: bool = True) -> str:
        """
        載入 Prompt 模板
        
        Args:
            prompt_name: Prompt 檔案名（不含副檔名）
            use_cache: 是否使用快取
            
        Returns:
            Prompt 內容
        """
        # 檢查快取
        if use_cache and prompt_name in self.cache:
            logger.debug(f"📦 使用快取 Prompt: {prompt_name}")
            return self.cache[prompt_name]
        
        # 嘗試 .txt 和 .md 副檔名
        for ext in ['.txt', '.md']:
            prompt_file = self.prompts_dir / f"{prompt_name}{ext}"
            if prompt_file.exists():
                break
        else:
            raise FileNotFoundError(f"Prompt 檔案不存在: {prompt_name}")
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 快取
        self.cache[prompt_name] = content
        logger.info(f"📄 載入 Prompt: {prompt_name} ({len(content)} 字元)")
        
        return content
    
    def reload(self, prompt_name: Optional[str] = None):
        """
        重新載入 Prompt
        
        Args:
            prompt_name: 指定 Prompt 名稱，None 則清空全部快取
        """
        if prompt_name:
            if prompt_name in self.cache:
                del self.cache[prompt_name]
                logger.info(f"🔄 清除 Prompt 快取: {prompt_name}")
        else:
            self.cache.clear()
            logger.info("🔄 清除所有 Prompt 快取")
    
    def format(self, prompt_name: str, **kwargs) -> str:
        """
        載入並格式化 Prompt（替換變數）
        
        Args:
            prompt_name: Prompt 檔案名
            **kwargs: 要替換的變數
            
        Returns:
            格式化後的 Prompt
            
        Example:
            prompt = loader.format("greeting", name="Alice")
            # 如果 greeting.txt 內容是 "Hello {name}!"
            # 返回 "Hello Alice!"
        """
        template = self.load(prompt_name)
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"❌ Prompt 變數缺失: {e}")
            raise


# ==================== 配置驗證器 ====================

class ConfigValidator:
    """配置驗證器"""
    
    @staticmethod
    def validate_llm_config(config: Dict[str, Any]) -> bool:
        """
        驗證 LLM 配置
        
        Args:
            config: 配置字典
            
        Returns:
            是否通過驗證
            
        Raises:
            ValueError: 驗證失敗
        """
        # 檢查必要欄位
        if 'generation_config' not in config:
            raise ValueError("配置缺少 generation_config")
        
        gen_config = config['generation_config']
        
        # 驗證 temperature
        if 'temperature' in gen_config:
            temp = gen_config['temperature']
            if not isinstance(temp, (int, float)):
                raise ValueError(f"temperature 必須是數字，當前類型: {type(temp)}")
            if not 0.0 <= temp <= 1.0:
                raise ValueError(f"temperature 必須在 0.0-1.0 之間，當前值: {temp}")
        
        # 驗證 top_p
        if 'top_p' in gen_config:
            top_p = gen_config['top_p']
            if not isinstance(top_p, (int, float)):
                raise ValueError(f"top_p 必須是數字")
            if not 0.0 <= top_p <= 1.0:
                raise ValueError(f"top_p 必須在 0.0-1.0 之間，當前值: {top_p}")
        
        # 驗證 top_k
        if 'top_k' in gen_config:
            top_k = gen_config['top_k']
            if not isinstance(top_k, int):
                raise ValueError(f"top_k 必須是整數")
            if top_k < 1:
                raise ValueError(f"top_k 必須 >= 1，當前值: {top_k}")
        
        # 驗證 max_output_tokens
        if 'max_output_tokens' in gen_config:
            max_tokens = gen_config['max_output_tokens']
            if not isinstance(max_tokens, int):
                raise ValueError(f"max_output_tokens 必須是整數")
            if max_tokens < 1:
                raise ValueError(f"max_output_tokens 必須 >= 1")
        
        logger.info("✅ LLM 配置驗證通過")
        return True


# ==================== 工具函數 ====================

def ensure_dir(path: Union[str, Path]) -> Path:
    """
    確保目錄存在，不存在則建立
    
    Args:
        path: 目錄路徑
        
    Returns:
        Path 物件
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_text_file(file_path: Union[str, Path], encoding: str = 'utf-8') -> str:
    """
    載入文字檔案
    
    Args:
        file_path: 檔案路徑
        encoding: 編碼
        
    Returns:
        檔案內容
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"檔案不存在: {file_path}")
    
    with open(file_path, 'r', encoding=encoding) as f:
        return f.read()


# ==================== 使用範例 ====================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 範例 1: 載入 JSON 配置
    print("\n範例 1: JSON 配置")
    config_loader = ConfigLoader("config/example.json")
    config = config_loader.load()
    print(f"Temperature: {config_loader.get('temperature', 0.5)}")
    
    # 範例 2: 載入 YAML 配置
    print("\n範例 2: YAML 配置")
    yaml_loader = ConfigLoader("config/example.yaml")
    yaml_config = yaml_loader.load()
    print(f"Model: {yaml_loader.get('model_name')}")
    
    # 範例 3: 載入 Prompt
    print("\n範例 3: Prompt 載入")
    prompt_loader = PromptLoader("prompts/")
    system_prompt = prompt_loader.load("system_role")
    print(f"Prompt 長度: {len(system_prompt)}")
    
    # 範例 4: Prompt 格式化
    print("\n範例 4: Prompt 格式化")
    formatted = prompt_loader.format("greeting", name="遊俠", game="阿瓦隆")
    print(formatted)
    
    # 範例 5: 配置驗證
    print("\n範例 5: 配置驗證")
    try:
        ConfigValidator.validate_llm_config({
            "generation_config": {
                "temperature": 0.3,
                "top_p": 0.95
            }
        })
    except ValueError as e:
        print(f"驗證失敗: {e}")