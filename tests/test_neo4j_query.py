#!/usr/bin/env python3
"""
Quick test script to run Cypher queries against the Neo4j database.
Usage: docker exec mre_rag-app-1 python3 /app/tests/test_neo4j_query.py "MATCH (n) RETURN count(n) as count"
"""

import asyncio
import os
import argparse
import sys
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

async def main():
    parser = argparse.ArgumentParser(description="Run a quick Neo4j Cypher query.")
    parser.add_argument("query", type=str, help="The Cypher query to execute")
    args = parser.parse_args()

    load_dotenv()
    
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
    neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')
    
    print(f"🔗 Connecting to Neo4j at {neo4j_uri}...")
    driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        # Verify connection
        await driver.verify_connectivity()
        
        print(f"🔍 Executing Query:\n{args.query}\n{'-'*60}")
        async with driver.session() as session:
            result = await session.run(args.query)
            
            records = [dict(record) async for record in result]
            
            if not records:
                print("No results found.")
            else:
                for i, record in enumerate(records, 1):
                    # Format output nicely
                    formatted_record = ", ".join(f"{k}: {v}" for k, v in record.items())
                    print(f"{i:2d}. {formatted_record}")
                    
            print(f"{'-'*60}\n✅ Query executed successfully. Returned {len(records)} records.")
            
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(main())
