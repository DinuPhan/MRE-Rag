import os
import re
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import uuid
import logging
from src.reranker import RerankerManager

logger = logging.getLogger(__name__)

# Global Collection Constants
PROSE_COLLECTION = "knowledge_prose"
CODE_COLLECTION = "knowledge_code"

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
                logger.info(f"Connected to Qdrant server at {qdrant_url}")
            except Exception as e:
                logger.warning(f"Failed to connect to Qdrant server at {qdrant_url}: {e}. Falling back to in-memory storage.")
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
        Also guarantees that the `url` payload field is indexed for fast metadata filtering.
        """
        collections = self.client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)
        
        if not exists:
            logger.info(f"Creating Qdrant collection: {collection_name}")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
            logger.info(f"Creating payload index on 'url' for collection: {collection_name}")
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="url",
                field_schema="keyword",
            )
        else:
            logger.debug(f"Qdrant collection {collection_name} already exists.")

    def upsert_knowledge_chunks(self, collection_name: str, chunks: List[str], vectors: List[List[float]], metadatas: List[Dict[str, Any]]):
        """
        Upserts chunked text and their corresponding Gemini embeddings into Qdrant.
        """
        logger.debug(f"Upserting {len(chunks)} chunks into collection: {collection_name}")
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
        logger.info(f"Successfully inserted {len(points)} chunks into Qdrant collection {collection_name}.")

    def search(self, collection_name: str, query_vector: List[float], limit: int = 5, query_text: Optional[str] = None, url_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Performs a semantic search against the Qdrant database.
        Applies a fast Payload Index metadata filter if `url_filter` is provided.
        Optionally executes a two-stage retrieval cross-encoder reranking pass if `query_text` is provided.
        """
        logger.debug(f"Executing search on collection: {collection_name} | Limit: {limit} | Two-Stage: {bool(query_text)} | Filter: {url_filter}")
        self._ensure_collection_exists(collection_name)
        
        # Build the payload filter
        query_filter = None
        if url_filter:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="url",
                        match=MatchValue(value=url_filter)
                    )
                ]
            )
        
        # If cross-encoding, fetch a larger pool initially
        fetch_limit = max(limit * 10, 50) if query_text else limit
        logger.debug(f"Initial Bi-Encoder fetch limit set to: {fetch_limit}")
        
        search_result = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
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
            logger.debug(f"Triggering cross-encoder reranking on {len(results)} bi-encoder hits")
            documents = [res["content"] for res in results]
            reranked_indices = self.reranker.rerank(query=query_text, documents=documents, top_n=limit)
            
            final_results = []
            for idx in reranked_indices:
                if idx < len(results):
                    final_results.append(results[idx])
            return final_results
            
        return results
