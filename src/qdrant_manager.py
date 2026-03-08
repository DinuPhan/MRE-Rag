import os
import re
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import uuid
from src.reranker import RerankerManager

class QdrantManager:
    def __init__(self, vector_size: int = 3072):
        """
        Initializes the Qdrant Client.
        Default vector_size is 3072 matching Gemini's text-embedding-004/001 output.
        """
        qdrant_url = os.getenv("QDRANT_URL", "")
        qdrant_api_key = os.getenv("QDRANT_API_KEY", "")
        
        # Connect to Qdrant (Docker by default, fallback to local disk)
        if qdrant_url:
            try:
                self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key if qdrant_api_key else None)
                # Verify connection
                self.client.get_collections()
                print(f"Connected to Qdrant server at {qdrant_url}")
            except Exception as e:
                print(f"Failed to connect to Qdrant server at {qdrant_url}: {e}. Falling back to in-memory storage.")
                self.client = QdrantClient(location=":memory:")
        else:
            # Fallback to local in-memory mode
            self.client = QdrantClient(location=":memory:")
        
        self.vector_size = vector_size
        self.reranker = RerankerManager()

    @staticmethod
    def escape_url(url: str) -> str:
        """
        Escapes a URL to be a valid Qdrant collection name.
        Allows only alphanumeric, underdash, and hyphen.
        """
        return re.sub(r'[^a-zA-Z0-9_\-]', '_', url).strip('_')

    def _ensure_collection_exists(self, collection_name: str):
        """
        Checks if the collection exists, creates it if not.
        """
        collections = self.client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)
        
        if not exists:
            print(f"Creating Qdrant collection: {collection_name}")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
        else:
            print(f"Qdrant collection {collection_name} already exists.")

    def upsert_knowledge_chunks(self, collection_name: str, chunks: List[str], vectors: List[List[float]], metadatas: List[Dict[str, Any]]):
        """
        Upserts chunked text and their corresponding Gemini embeddings into Qdrant.
        """
        self._ensure_collection_exists(collection_name)
        
        if len(chunks) != len(vectors) or len(chunks) != len(metadatas):
            raise ValueError("Lengths of chunks, vectors, and metadatas must match.")
            
        points = []
        for i, (chunk, vector, metadata) in enumerate(zip(chunks, vectors, metadatas)):
            # Create a unique UUID for the point using URL and chunk index mapping
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, metadata.get('url', 'unknown') + f"_{i}"))
            
            # Combine text content with metadata payload
            payload = metadata.copy()
            payload['content'] = chunk
            
            point = PointStruct(
                id=point_id,
                vector=vector,
                payload=payload
            )
            points.append(point)
            
        # Perform the batch upsert
        self.client.upsert(
            collection_name=collection_name,
            points=points
        )
        print(f"Successfully inserted {len(points)} chunks into Qdrant collection {collection_name}.")

    def search(self, collection_name: str, query_vector: List[float], limit: int = 5, query_text: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Performs a semantic search against the Qdrant database.
        Optionally executes a two-stage retrieval cross-encoder reranking pass if `query_text` is provided.
        """
        self._ensure_collection_exists(collection_name)
        
        # If cross-encoding, fetch a larger pool initially
        fetch_limit = max(limit * 10, 50) if query_text else limit
        
        search_result = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=fetch_limit
        ).points
        
        # Format the rough bi-encoder results cleanly
        results = []
        for scored_point in search_result:
            results.append({
                "id": scored_point.id,
                "score": scored_point.score,
                "content": scored_point.payload.get("content", ""),
                "metadata": {k: v for k, v in scored_point.payload.items() if k != "content"}
            })
            
        # Secondary Stage: Cross-Encoder Reranking
        if query_text and results:
            documents = [res["content"] for res in results]
            reranked_indices = self.reranker.rerank(query=query_text, documents=documents, top_n=limit)
            
            final_results = []
            for idx in reranked_indices:
                if idx < len(results):
                    final_results.append(results[idx])
            return final_results
            
        return results

    def search_all(self, query_vector: List[float], limit: int = 5, query_text: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Performs a semantic search across all collections.
        """
        collections = self.client.get_collections().collections
        all_results = []
        
        # If reranking, we expand the fetch size across all collections, 
        # then rerank the global combined pool at once.
        fetch_limit = max(limit * 10, 50) if query_text else limit
        
        for c in collections:
            res = self.search(c.name, query_vector, limit=fetch_limit, query_text=None) # get raw bi-encoder results natively
            all_results.extend(res)
            
        # Sort by raw vector score descending and take top N logically across tables
        all_results.sort(key=lambda x: x["score"], reverse=True)
        all_results = all_results[:fetch_limit]
        
        # Global Cross-Encoder Reranking
        if query_text and all_results:
             documents = [res["content"] for res in all_results]
             reranked_indices = self.reranker.rerank(query=query_text, documents=documents, top_n=limit)
             final_results = []
             for idx in reranked_indices:
                 if idx < len(all_results):
                     final_results.append(all_results[idx])
             return final_results
             
        return all_results[:limit]

    def search_code(self, collection_name: str, query_vector: List[float], limit: int = 5, query_text: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Specialized search to retrieve isolated code blocks.
        The `_code` suffix is guaranteed by `RagPipeline`.
        """
        code_collection = f"{collection_name}_code"
        try:
            return self.search(code_collection, query_vector, limit=limit, query_text=query_text)
        except Exception as e:
            print(f"Code Collection Search Error (likely empty/nonexistent): {e}")
            return []
