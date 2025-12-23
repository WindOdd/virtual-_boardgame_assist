"""
Project Akka - Semantic Router Module
Responsibility: 
1. Load Embedding Model (sentence-transformers)
2. Build Vector Index from semantic_routes.yaml
3. Perform Cosine Similarity Search
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any

# 依賴檢查
try:
    from sentence_transformers import SentenceTransformer, util
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)

class SemanticRouter:
    def __init__(self, model_config: Dict[str, Any], routes_config: Dict[str, List[str]]):
        """
        Args:
            model_config: 來自 system_config.yaml 的 model.embedding 區塊
            routes_config: 來自 semantic_routes.yaml 的完整內容
        """
        self.model = None
        self.index = {}
        self.routes = routes_config
        self.model_name = model_config.get("name")
        self.threshold = model_config.get("threshold", 0.88) # 預設門檻值

        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("❌ sentence-transformers not installed. Semantic Router disabled.")
            return

        if not self.model_name:
            logger.error("❌ No embedding model name provided in config.")
            return

        self._init_model()
        self._build_index()

    def _init_model(self):
        try:
            logger.info(f"Loading Embedding Model: {self.model_name} ...")
            # device='cpu' 確保不搶佔 LLM 的 GPU 資源
            self.model = SentenceTransformer(self.model_name, device='cpu')
            logger.info("✅ Embedding Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model = None

    def _build_index(self):
        """Pre-compute vectors for all anchors."""
        if not self.model or not self.routes:
            return
        
        logger.info(f"Building vector index for {len(self.routes)} intents...")
        count = 0
        for intent, texts in self.routes.items():
            if not isinstance(texts, list): continue
            
            # [CRITICAL] E5 模型要求 "query: " 前綴
            # 這裡我們統一幫設定檔裡的句子加上前綴
            prefixed_texts = [f"query: {t}" for t in texts]
            
            # encode 回傳 Tensor，存入記憶體
            self.index[intent] = self.model.encode(prefixed_texts, convert_to_tensor=True)
            count += len(texts)
        
        logger.info(f"✅ Vector index built. Total anchors: {count}")

    def route(self, user_input: str) -> Tuple[Optional[str], float]:
        """
        Core Routing Logic
        Returns: (Best Intent, Confidence Score)
        """
        if not self.model or not self.index:
            return None, 0.0

        try:
            # [CRITICAL] 使用者輸入也要加上 "query: "
            prefixed_input = f"query: {user_input}"
            
            # 1. Encode user input
            user_embedding = self.model.encode(prefixed_input, convert_to_tensor=True)
            
            best_score = 0.0
            best_intent = None
            
            # 2. Compare against all anchors
            for intent, anchor_embeddings in self.index.items():
                # util.cos_sim 回傳相似度矩陣
                scores = util.cos_sim(user_embedding, anchor_embeddings)[0]
                max_score = float(scores.max()) # 取最像的那句
                
                if max_score > best_score:
                    best_score = max_score
                    best_intent = intent
            
            # 3. Threshold Check
            if best_score >= self.threshold:
                return best_intent, best_score
            
            return None, best_score

        except Exception as e:
            logger.error(f"Routing error: {e}")
            return None, 0.0