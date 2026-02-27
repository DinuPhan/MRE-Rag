import asyncio
import concurrent.futures
from typing import List, Dict, Any
from src.crawler import MreCrawler
from src.embeddings import EmbeddingManager
from src.qdrant_manager import QdrantManager
from src.chunking import IntelligentChunker, extract_code_blocks
from src.context_generator import ContextGenerator

class RagPipeline:
    def __init__(self):
        """
        Orchestrates Crawler, Embeddings, and Vector Store.
        """
        self.crawler = MreCrawler()
        self.embeddings = EmbeddingManager()
        self.qdrant = QdrantManager(vector_size=self.embeddings.dimension)
        self.chunker = IntelligentChunker(chunk_size=1500)
        self.context_generator = None  # Lazy load to avoid instant API key checks

    def chunk_text(self, text: str, chunk_size: int = 1500) -> List[str]:
        """
        Deprecated: Native naive chunking. Preserved for backward compatibility.
        Routes to the new IntelligentChunker.
        """
        if chunk_size != getattr(self.chunker, 'chunk_size', 1500):
            self.chunker.chunk_size = chunk_size
        return self.chunker.chunk_text(text)

    async def ingest_url(self, url: str, max_depth: int = 0, max_pages: int = 10, enable_contextual_ai: bool = False) -> dict:
        """
        Crawls a URL (or sitemap/.txt), chunks the content from all pages, embeds them, and saves to Qdrant.
        When enable_contextual_ai=True, extracts code snippets and uses Gemini to write a title for them before embedding.
        """
        if enable_contextual_ai and not self.context_generator:
            self.context_generator = ContextGenerator()
            
        # 1. Crawl
        crawl_results = await self.crawler.crawl_urls(url, max_depth=max_depth, max_pages=max_pages)
        if not crawl_results:
            return {"success": False, "error": "No pages were successfully crawled."}
            
        all_chunks = []
        all_metadatas = []
        
        all_code_chunks = []
        all_code_metadatas = []
        
        # 2. Chunk and Extract
        for crawl_result in crawl_results:
            markdown = crawl_result["markdown"]
            page_url = crawl_result["url"]
            title = crawl_result["title"]
            
            # --- Standard Prose Chunking ---
            chunks = self.chunk_text(markdown)
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadatas.append({
                    "url": page_url,
                    "title": title,
                    "chunk_index": i
                })
                
            # --- Code Snippet Extraction ---
            code_blocks = extract_code_blocks(markdown)
            for i, block in enumerate(code_blocks):
                code_text = block['code']
                
                # Default "dumb" formatting
                embedding_payload = f"Code Snippet:\n{code_text}"
                
                # Contextual AI "Smart" formatting
                if enable_contextual_ai:
                    ai_title = self.context_generator.generate_code_example_title(
                        code_text, block['context_before'], block['context_after']
                    )
                    embedding_payload = f"Title: {ai_title}\n\nCode Snippet:\n{code_text}"

                all_code_chunks.append(embedding_payload) # The Vector DB gets the titled payload
                all_code_metadatas.append({
                    "url": page_url,
                    "title": title,
                    "code_index": i,
                    "language": block['language'],
                    "raw_code": code_text # We keep a clean raw copy in the metadata for exact retrieval!
                })
                
        if not all_chunks:
            return {"success": False, "error": "No text extracted to chunk from any page."}
            
        print(f"Extracted {len(all_chunks)} prose chunks and {len(all_code_chunks)} code snippets from {len(crawl_results)} pages.")
        
        # 3. Embed (in batches to avoid overwhelming the Embedding API payload limits)
        vectors = []
        code_vectors = []
        try:
            batch_size = 100
            
            # Helper function for ThreadPoolExecutor
            def _embed_batch(batch):
                return self.embeddings.create_embeddings_batch(batch)

            # Concurrent Prose Embedding
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                prose_batches = [all_chunks[i:i + batch_size] for i in range(0, len(all_chunks), batch_size)]
                for result in executor.map(_embed_batch, prose_batches):
                    vectors.extend(result)
                    
            # Concurrent Code Embedding
            if all_code_chunks:
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    code_batches = [all_code_chunks[i:i + batch_size] for i in range(0, len(all_code_chunks), batch_size)]
                    for result in executor.map(_embed_batch, code_batches):
                        code_vectors.extend(result)
                        
        except Exception as e:
            return {"success": False, "error": f"Embedding generator failed: {str(e)}"}
            
        # 4. Insert
        # We group all sub-pages under the collection name of the initial target URL
        collection_name = QdrantManager.escape_url(url)
        
        # Upsert Standard Prose
        self.qdrant.upsert_knowledge_chunks(collection_name, all_chunks, vectors, all_metadatas)
        
        # Upsert Code Snippets
        if all_code_chunks:
            self.qdrant.upsert_knowledge_chunks(f"{collection_name}_code", all_code_chunks, code_vectors, all_code_metadatas)
        
        return {
            "success": True,
            "message": f"Successfully ingested {len(crawl_results)} pages into Qdrant collection '{collection_name}'.",
            "chunks_processed": len(all_chunks),
            "code_snippets_processed": len(all_code_chunks),
            "pages_processed": len(crawl_results),
            "contextual_ai_used": enable_contextual_ai
        }

    def query(self, text: str, url: str = None, limit: int = 5, code_search: bool = False) -> List[Dict[str, Any]]:
        """
        Queries the Qdrant database using Gemini embedding on the query.
        When code_search=True, semantically expands the query to match AI contextual code prefixes.
        """
        try:
            # Enhanced Query Expansion for Code Search
            if code_search:
                query_text = f"Code example for {text}\n\nSummary: Example code showing {text}"
            else:
                query_text = text
                
            query_vector = self.embeddings.create_embedding(query_text)
            
            if url:
                collection_name = QdrantManager.escape_url(url)
                if code_search:
                    return self.qdrant.search_code(collection_name, query_vector=query_vector, limit=limit)
                else:
                    return self.qdrant.search(collection_name, query_vector=query_vector, limit=limit)
            else:
                # search_all currently doesn't natively fork prose vs code, so it searches global default logic
                return self.qdrant.search_all(query_vector=query_vector, limit=limit)
        except Exception as e:
            print(f"Query Error: {e}")
            return []

if __name__ == "__main__":
    pipeline = RagPipeline()
    query_text = "What is this document about?"
    results = pipeline.query(query_text)
    print("Test Query Result: ", results)
