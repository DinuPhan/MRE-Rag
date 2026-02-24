import os
from typing import List, Any
from google import genai
from dotenv import load_dotenv
import httpx

# Load environment variables
load_dotenv()

class BaseEmbeddingProvider:
    @property
    def dimension(self) -> int:
        raise NotImplementedError

    def create_embedding(self, text: str) -> List[float]:
        raise NotImplementedError

    def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, model_name: str = "models/gemini-embedding-001"):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
            
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name
        self._dimension = 3072

    @property
    def dimension(self) -> int:
        return self._dimension

    def create_embedding(self, text: str) -> List[float]:
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=text,
            config=genai.types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        return response.embeddings[0].values

    def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=texts,
            config=genai.types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        return [emb.values for emb in response.embeddings]


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self):
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
            
        self.model_name = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self._dimension = int(os.getenv("OPENAI_EMBEDDING_DIMENSION", "1536"))

    @property
    def dimension(self) -> int:
        return self._dimension

    def _post_embeddings(self, input_data: Any) -> Any:
        # Standard OpenAI API request payload
        payload = {
            "model": self.model_name,
            "input": input_data
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # HTTPX automatically handles connection pooling within this context, 
        # but for standalone simplicity we use a client per request in the minimal example.
        with httpx.Client() as client:
            response = client.post(f"{self.base_url}/embeddings", headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            return response.json()

    def create_embedding(self, text: str) -> List[float]:
        result = self._post_embeddings(text)
        return result["data"][0]["embedding"]

    def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        result = self._post_embeddings(texts)
        # OpenAI returns an array of objects matching the batch order
        sorted_data = sorted(result["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]


class InhouseEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self):
        self.base_url = os.getenv("INHOUSE_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")
        self.api_key = os.getenv("INHOUSE_API_KEY", "")
        self._dimension = int(os.getenv("INHOUSE_EMBEDDING_DIMENSION", "768"))

    @property
    def dimension(self) -> int:
        return self._dimension

    def _post_embeddings(self, sentences: list) -> List[List[float]]:
        # Required format for /api/v1/bi_encoder/encode: {"sentences": [...]}
        payload = {
            "sentences": sentences
        }
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        with httpx.Client() as client:
            response = client.post(f"{self.base_url}/bi_encoder/encode", headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            return response.json() # Assuming the endpoint returns List[List[float]] directly or adapt as needed

    def create_embedding(self, text: str) -> List[float]:
        result = self._post_embeddings([text])
        if isinstance(result, dict) and "embeddings" in result:
             # Graceful handling if they wrapped the list
             return result["embeddings"][0]
        return result[0]

    def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        result = self._post_embeddings(texts)
        if isinstance(result, dict) and "embeddings" in result:
             return result["embeddings"]
        return result


class EmbeddingManager:
    """
    Factory Router. Abstracts away embedding operations natively utilizing internal Providers dynamically.
    """
    def __init__(self):
        provider_type = os.getenv("EMBEDDING_PROVIDER", "GEMINI").upper()
        
        if provider_type == "OPENAI":
            print(f"Initializing OpenAI Embedding Provider at {os.getenv('OPENAI_BASE_URL')}")
            self._provider = OpenAIEmbeddingProvider()
        elif provider_type == "INHOUSE":
            print(f"Initializing In-House Embedding Provider at {os.getenv('INHOUSE_BASE_URL')}")
            self._provider = InhouseEmbeddingProvider()
        else:
            print("Initializing standard Gemini Embedding Provider")
            self._provider = GeminiEmbeddingProvider()

    @property
    def dimension(self) -> int:
        return self._provider.dimension

    def create_embedding(self, text: str) -> List[float]:
        try:
            return self._provider.create_embedding(text)
        except Exception as e:
            print(f"Error generating embedding via {type(self._provider).__name__}: {e}")
            raise

    def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        try:
            return self._provider.create_embeddings_batch(texts)
        except Exception as e:
            print(f"Error generating batch embeddings via {type(self._provider).__name__}: {e}")
            raise
