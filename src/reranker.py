import os
from typing import List, Dict, Any
import httpx

class BaseReranker:
    def rerank(self, query: str, documents: List[str], top_n: int = 5) -> List[int]:
        """
        Takes a query and a list of document strings.
        Returns the indexes of documents sorted from highest relevance to lowest relevance.
        Typically returns only the `top_n` indexes.
        """
        raise NotImplementedError

class NoOpReranker(BaseReranker):
    """
    A pass-through reranker used as a fallback if no actual reranker provider is configured.
    It simply returns the original indexes in order.
    """
    def rerank(self, query: str, documents: List[str], top_n: int = 5) -> List[int]:
        return list(range(len(documents)))[:top_n]

class InhouseReranker(BaseReranker):
    def __init__(self):
        self.base_url = os.getenv("INHOUSE_RERANKER_BASE_URL", "http://localhost:8000/api/v1/cross_encoder/score")
        self.api_key = os.getenv("INHOUSE_RERANKER_API_KEY", "")
        self.model = os.getenv("INHOUSE_RERANKER_MODEL", "inhouse-reranker-default")

    def rerank(self, query: str, documents: List[str], top_n: int = 5) -> List[int]:
        if not documents:
            return []

        # Prepare text_pairs: [ ["query", "doc1"], ["query", "doc2"] ]
        text_pairs = [[query, doc] for doc in documents]
        
        payload = {
            "model": self.model,
            "text_pairs": text_pairs,
            "max_seq_length": 512,
            "client": "api"
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            with httpx.Client() as client:
                response = client.post(
                    self.base_url, 
                    headers=headers, 
                    json=payload, 
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                # Extract scores from the expected schema: {"scores": [... float ...]}
                if "scores" in data and isinstance(data["scores"], list):
                    scores = data["scores"]
                    
                    if len(scores) != len(documents):
                        print(f"Warning: In-house reranker returned {len(scores)} scores for {len(documents)} documents.")
                    
                    # Pair indices with their scores, sort descending by score
                    scored_indices = [(index, score) for index, score in enumerate(scores)]
                    scored_indices.sort(key=lambda x: x[1], reverse=True)
                    
                    # Return only the top_n indices
                    return [idx for idx, _ in scored_indices[:top_n]]
                else:
                    print(f"Unexpected response format from in-house reranker. Expected 'scores' list. Got: {data}")
                    return list(range(len(documents)))[:top_n]
                    
        except Exception as e:
            print(f"Error executing in-house reranker for query '{query}': {e}")
            return list(range(len(documents)))[:top_n]

class RerankerManager:
    """
    Factory Router. Abstracts away reranking operations natively utilizing internal Providers dynamically.
    """
    def __init__(self):
        provider_type = os.getenv("RERANKER_PROVIDER", "NONE").upper()
        
        if provider_type == "INHOUSE":
            print(f"Initializing In-House Reranker Provider at {os.getenv('INHOUSE_RERANKER_BASE_URL')}")
            self._provider = InhouseReranker()
        else:
            print("No external Reranker provider detected (or set to NONE). Initializing Pass-Through Baseline.")
            self._provider = NoOpReranker()

    def rerank(self, query: str, documents: List[str], top_n: int = 5) -> List[int]:
        """
        Returns the sorted indices of the most relevant documents.
        """
        try:
            return self._provider.rerank(query, documents, top_n)
        except Exception as e:
            print(f"Reranking error: {e}. Falling back to default order.")
            return list(range(len(documents)))[:top_n]
