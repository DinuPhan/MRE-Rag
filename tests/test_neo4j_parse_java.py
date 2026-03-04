#!/usr/bin/env python3
"""
Custom script to parse the imgscalr repository and query for Chris Campbell's algorithm.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.knowledge_graphs.parse_repo_into_neo4j import DirectNeo4jExtractor

async def main():
    load_dotenv()
    
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
    neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')
    
    extractor = DirectNeo4jExtractor(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        await extractor.initialize()
        
        # Analyze the imgscalr repository
        repo_url = "https://github.com/rkalla/imgscalr.git"
        print(f"\\n--- Parsing Repository: {repo_url} ---")
        await extractor.analyze_repository(repo_url)
        
        # Now query for Chris Campbell's incremental scaling algorithm
        print("\\n--- Querying for Chris Campbell's algorithm ---")
        async with extractor.driver.session() as session:
            # We want to search for 'increment' in methods
            query = """
            MATCH (m:Method)
            WHERE toLower(m.name) CONTAINS 'increment' OR toLower(m.name) CONTAINS 'campbell'
            RETURN m.name as method_name, m.full_name as full_name, m.args as args, m.return_type as return_type
            """
            result = await session.run(query)
            
            records = [dict(record) async for record in result]
            
            if records:
                print("Found relevant methods:")
                for r in records:
                    print(f" - {r['full_name']}({', '.join(r['args'])}): {r['return_type']}")
            else:
                print("No structurally matching methods found based on name ('increment' or 'campbell').")
                
                # Check for attributes
                attr_query = """
                MATCH (a:Attribute)
                WHERE toLower(a.name) CONTAINS 'increment' OR toLower(a.name) CONTAINS 'campbell'
                RETURN a.name as attr_name, a.full_name as full_name
                """
                attr_result = await session.run(attr_query)
                attr_records = [dict(r) async for r in attr_result]
                
                if attr_records:
                    print("Found relevant attributes:")
                    for a in attr_records:
                        print(f" - {a['full_name']}")
                else:
                    print("No attributes or methods found containing 'increment' or 'campbell'. Note that structural parsing does not include comments.")
                    
            print("\\n--- End of Execution ---")
            
    finally:
        await extractor.close()

if __name__ == "__main__":
    asyncio.run(main())
