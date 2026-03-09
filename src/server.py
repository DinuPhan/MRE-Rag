from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
from contextlib import asynccontextmanager
import sys
import os
import tempfile
from pathlib import Path
from neo4j import AsyncGraphDatabase

from mcp.server.fastmcp import FastMCP
from rag_pipeline import RagPipeline

# Add knowledge_graphs to path to resolve its internal relative imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'knowledge_graphs'))

from knowledge_graphs.parse_repo_into_neo4j import DirectNeo4jExtractor
from knowledge_graphs.ai_hallucination_detector import AIHallucinationDetector

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
    max_depth: Optional[int] = None
    max_pages: Optional[int] = None

class QueryRequest(BaseModel):
    query: str
    url: Optional[str] = None
    limit: int = 5

class QueryResponse(BaseModel):
    results: List[Dict[str, Any]]

# Define Pydantic models for Knowledge Graph REST endpoints
class ParseRepoRequest(BaseModel):
    repo_url: str
    incremental: bool = True

class GraphQueryRequest(BaseModel):
    query: str

class ValidateScriptRequest(BaseModel):
    script_content: str
    language: str = "python"

# ==========================================
# 1. FastAPI Setup (REST)
# ==========================================
import logging
from rich.logging import RichHandler

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("mre-rag")

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
        result = await pipeline.ingest_url(
            request.url, 
            max_depth=request.max_depth,
            max_pages=request.max_pages
        )
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

@app.post("/knowledge_graph/parse")
async def kg_parse_endpoint(request: ParseRepoRequest):
    """
    REST Endpoint: Pull a GitHub repository and parse it into the Neo4j Knowledge Graph.
    """
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
    neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')
    extractor = DirectNeo4jExtractor(neo4j_uri, neo4j_user, neo4j_password)
    try:
        await extractor.initialize()
        await extractor.analyze_repository(request.repo_url)
        return {"success": True, "message": f"Successfully parsed repository: {request.repo_url}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await extractor.close()

@app.post("/knowledge_graph/query")
async def kg_query_endpoint(request: GraphQueryRequest):
    """
    REST Endpoint: Execute a raw Cypher query against the Neo4j Knowledge Graph.
    """
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
    neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')
    driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    try:
        await driver.verify_connectivity()
        async with driver.session() as session:
            result = await session.run(request.query)
            records = [dict(record) async for record in result]
            return {"success": True, "records": records, "count": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await driver.close()

@app.post("/knowledge_graph/validate")
async def kg_validate_endpoint(request: ValidateScriptRequest):
    """
    REST Endpoint: Accept a raw script string and validate it against the Neo4j Knowledge Graph for hallucinations.
    """
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
    neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')
    detector = AIHallucinationDetector(neo4j_uri, neo4j_user, neo4j_password)
    
    # Create temp file to run detector against
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.py', delete=False) as temp_file:
        temp_file.write(request.script_content)
        temp_file_path = temp_file.name
        
    try:
        await detector.initialize()
        report = await detector.detect_hallucinations(
            script_path=temp_file_path,
            output_dir=str(Path(temp_file_path).parent),
            save_json=True,
            save_markdown=False,
            print_summary=False
        )
        return {"success": True, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await detector.close()
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# ==========================================
# 2. FastMCP Setup (Cursor / Windsurf integration)
# ==========================================
mcp = FastMCP("mre-rag-mcp")

@mcp.tool()
async def crawl_website(url: str, max_depth: int = None, max_pages: int = None) -> str:
    """
    Crawl a web page (or .xml sitemap), extract markdown, generate embeddings, and store in Qdrant.
    It will also export local raw text chunks (llms.txt format).
    Specify max_depth>0 to recursively discover internal links.
    """
    try:
        result = await pipeline.ingest_url(url, max_depth=max_depth, max_pages=max_pages)
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

@mcp.tool()
async def parse_repository(repo_url: str, incremental: bool = True) -> str:
    """
    Pull a GitHub repository and parse it into the Neo4j Knowledge Graph using tree-sitter structure mapping.
    """
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
    neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')
    extractor = DirectNeo4jExtractor(neo4j_uri, neo4j_user, neo4j_password)
    try:
        await extractor.initialize()
        await extractor.analyze_repository(repo_url)
        return f"Successfully parsed repository: {repo_url} into Knowledge Graph."
    except Exception as e:
        return f"Error parsing repository {repo_url}: {str(e)}"
    finally:
        await extractor.close()

@mcp.tool()
async def query_knowledge_graph(cypher_query: str) -> str:
    """
    Execute a raw Cypher query against the Neo4j Knowledge Graph and return the output as a formatted string.
    """
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
    neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')
    driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    try:
        await driver.verify_connectivity()
        async with driver.session() as session:
            result = await session.run(cypher_query)
            records = [dict(record) async for record in result]
            if not records:
                return "No records returned for the query."
            formatted_out = f"Query returned {len(records)} records:\\n"
            for i, record in enumerate(records, 1):
                formatted_out += f"{i}. " + ", ".join(f"{k}: {v}" for k, v in record.items()) + "\\n"
            return formatted_out
    except Exception as e:
        return f"Error executing Cypher query: {str(e)}"
    finally:
        await driver.close()

@mcp.tool()
async def detect_code_hallucination(script_content: str) -> str:
    """
    Use the Neo4j Knowledge Graph to validate a raw python script string and detect hallucinated libraries, classes, methods, and functions.
    """
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
    neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')
    detector = AIHallucinationDetector(neo4j_uri, neo4j_user, neo4j_password)
    
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.py', delete=False) as temp_file:
        temp_file.write(script_content)
        temp_file_path = temp_file.name
        
    try:
        await detector.initialize()
        report = await detector.detect_hallucinations(
            script_path=temp_file_path,
            output_dir=str(Path(temp_file_path).parent),
            save_json=True,
            save_markdown=False,
            print_summary=False
        )
        # Summarize for the LLM
        summary = report['validation_summary']
        return f"""Validation Complete (Overall Confidence: {summary['overall_confidence']:.1%})
- Validations: {summary['total_validations']}
- Valid: {summary['valid_count']}
- Invalid (Hallucinations): {summary['invalid_count']}
- Not Found: {summary['not_found_count']}
- Uncertain: {summary['uncertain_count']}
- Hallucination Rate: {summary['hallucination_rate']:.1%}
"""
    except Exception as e:
        return f"Error executing hallucination detection: {str(e)}"
    finally:
        await detector.close()
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# Note: If running a pure MCP service, one would execute mcp.run()
# Here we are running FastAPI natively as it serves our core REST needs.

if __name__ == "__main__":
    # Provides both the standard FastAPI /docs interface and the MCP interface route
    uvicorn.run("server:app", host="0.0.0.0", port=8051)
