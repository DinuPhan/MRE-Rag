import argparse
from typing import List, Dict, Any
from src.qdrant_client import QdrantManager
from src.embeddings import EmbeddingManager
import json

def main():
    parser = argparse.ArgumentParser(description="Query the local Qdrant RAG database.")
    parser.add_argument("query", type=str, help="Search query to execute against the knowledge base.")
    parser.add_argument("--limit", type=int, default=5, help="Number of results to return.")
    
    args = parser.parse_args()
    
    # Initialize standalone managers
    embeddings = EmbeddingManager()
    qdrant = QdrantManager()
    
    print(f"Generating embedding for query: '{args.query}' using {embeddings.model_name}...")
    try:
        query_vector = embeddings.create_embedding(args.query)
    except Exception as e:
        print(f"Failed to generate embedding: {e}")
        return
        
    print(f"Querying Qdrant... (Limit: {args.limit})")
    try:
        results = qdrant.search(query_vector=query_vector, limit=args.limit)
    except Exception as e:
        print(f"Failed to query Qdrant: {e}")
        return
        
    if not results:
        print("No results found.")
        return
        
    print(f"\nFound {len(results)} results:\n" + "="*50)
    for i, res in enumerate(results):
        score = round(res['score'], 4)
        url = res['metadata'].get('url', 'Unknown')
        print(f"\n[Result {i+1}] Score: {score}")
        print(f"Source: {url}")
        print(f"Content :\n{res['content'][:500]}...")
        if len(res['content']) > 500:
            print("... (truncated)")
        print("-" * 50)

if __name__ == "__main__":
    main()
