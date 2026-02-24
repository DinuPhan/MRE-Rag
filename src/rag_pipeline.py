import asyncio
from typing import List, Dict, Any
from crawler import MreCrawler
from embeddings import EmbeddingManager
from qdrant_manager import QdrantManager

class RagPipeline:
    def __init__(self):
        """
        Orchestrates Crawler, Embeddings, and Vector Store.
        """
        self.crawler = MreCrawler()
        self.embeddings = EmbeddingManager()
        self.qdrant = QdrantManager(vector_size=self.embeddings.dimension)

    def chunk_text(self, text: str, chunk_size: int = 1500) -> List[str]:
        """
        Naive chunking function for text.
        Splits by characters but tries to respect paragraphs where possible.
        """
        chunks = []
        paragraphs = text.split("\n\n")
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) <= chunk_size:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
            
        return chunks

    async def ingest_url(self, url: str) -> dict:
        """
        Crawls a URL, chunks the content, embeds it using Gemini, and saves to Qdrant.
        """
        # 1. Crawl
        crawl_result = await self.crawler.crawl_url(url)
        if not crawl_result.get("success"):
            return {"success": False, "error": crawl_result.get("error")}
            
        markdown = crawl_result["markdown"]
        title = crawl_result["title"]
        
        # 2. Chunk
        chunks = self.chunk_text(markdown)
        if not chunks:
            return {"success": False, "error": "No text extracted to chunk"}
            
        print(f"Extracted {len(chunks)} chunks from {url}")
        
        # 3. Embed
        # Qdrant batch upserts are faster when embedded together
        try:
            vectors = self.embeddings.create_embeddings_batch(chunks)
        except Exception as e:
            return {"success": False, "error": str(e)}
            
        # 4. Meta packaging
        metadatas = []
        for i in range(len(chunks)):
            metadatas.append({
                "url": url,
                "title": title,
                "chunk_index": i
            })
            
        # 5. Insert
        collection_name = QdrantManager.escape_url(url)
        self.qdrant.upsert_knowledge_chunks(collection_name, chunks, vectors, metadatas)
        
        return {
            "success": True,
            "message": f"Successfully ingested {url} into Qdrant.",
            "chunks_processed": len(chunks)
        }

    def query(self, text: str, url: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Queries the Qdrant database using Gemini embedding on the query.
        """
        try:
            query_vector = self.embeddings.create_embedding(text)
            if url:
                collection_name = QdrantManager.escape_url(url)
                return self.qdrant.search(collection_name, query_vector=query_vector, limit=limit)
            else:
                return self.qdrant.search_all(query_vector=query_vector, limit=limit)
        except Exception as e:
            print(f"Query Error: {e}")
            return []

if __name__ == "__main__":
    pipeline = RagPipeline()
    query_text = "What is this document about?"
    results = pipeline.query(query_text)
    print("Test Query Result: ", results)
