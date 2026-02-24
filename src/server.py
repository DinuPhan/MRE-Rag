from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from rag_pipeline import RagPipeline

# Ensure we properly instantiate the pipeline within the FastAPI app lifespan
# to avoid SQLite multi-process locks when Uvicorn boots.
pipeline: RagPipeline = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    print("Initializing RAG Pipeline...")
    pipeline = RagPipeline()
    yield
    print("Shutting down RAG Pipeline...")

# Define Pydantic models for REST endpoints
class CrawlRequest(BaseModel):
    url: str

class QueryRequest(BaseModel):
    query: str
    url: Optional[str] = None
    limit: int = 5

class QueryResponse(BaseModel):
    results: List[Dict[str, Any]]

# ==========================================
# 1. FastAPI Setup (REST)
# ==========================================
app = FastAPI(
    title="MRE RAG Server", 
    description="Qdrant + Gemini Crawl and RAG Pipeline",
    lifespan=lifespan
)

@app.post("/crawl")
async def crawl_endpoint(request: CrawlRequest):
    """
    REST Endpoint: Crawl a URL and ingest it into the Qdrant vector database.
    """
    try:
        result = await pipeline.ingest_url(request.url)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error"))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=QueryResponse)
def query_endpoint(request: QueryRequest):
    """
    REST Endpoint: Query the Qdrant vector database using Gemini embeddings.
    """
    try:
        results = pipeline.query(request.query, url=request.url, limit=request.limit)
        return QueryResponse(results=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 2. FastMCP Setup (Cursor / Windsurf integration)
# ==========================================
mcp = FastMCP("mkre-rag-mcp")

@mcp.tool()
async def crawl_single_page(url: str) -> str:
    """
    Crawl a single web page, extract markdown, generate Gemini embeddings, and store in Qdrant.
    It will also export a local raw text chunk (llms.txt format).
    """
    try:
        result = await pipeline.ingest_url(url)
        if result.get("success"):
            return result.get("message", "Success")
        else:
            return f"Error crawling {url}: {result.get('error')}"
    except Exception as e:
         return f"Critical exception during crawl execution on {url}: {str(e)}"

@mcp.tool()
def perform_rag_query(query: str, url: str = None, limit: int = 5) -> str:
    """
    Semantic search over previously crawled documentation stored in Qdrant.
    Uses Gemini embeddings.
    """
    try:
        results = pipeline.query(query, url=url, limit=limit)
        if not results:
            return "No relevant documentation found."
            
        formatted_str = ""
        for idx, res in enumerate(results):
            score = round(res['score'], 3)
            url = res['metadata'].get('url', 'Unknown Source')
            formatted_str += f"\n--- Result {idx + 1} (Score: {score}) ---\n"
            formatted_str += f"Source: {url}\n"
            formatted_str += f"Content Snippet: {res['content'][:500]}...\n"
        return formatted_str
    except Exception as e:
         return f"Error querying Qdrant: {str(e)}"

# Note: If running a pure MCP service, one would execute mcp.run()
# Here we are running FastAPI natively as it serves our core REST needs.

if __name__ == "__main__":
    # Provides both the standard FastAPI /docs interface and the MCP interface route
    uvicorn.run("server:app", host="0.0.0.0", port=8051)
