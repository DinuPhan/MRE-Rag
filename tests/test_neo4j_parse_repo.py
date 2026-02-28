import os
import sys
import asyncio

# Add the src directory to the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from knowledge_graphs.parse_repo_into_neo4j import DirectNeo4jExtractor
import logging

# Configure basic logging for the script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def main():
    """Test parsing the MRE-Rag repository into Neo4j."""
    
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
    neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')
    
    print(f"Connecting to Neo4j at {neo4j_uri}...")
    extractor = DirectNeo4jExtractor(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        await extractor.initialize()
        
        repo_url = "https://github.com/DinuPhan/MRE-Rag.git"
        print(f"\\n=== Analyzing repository: {repo_url} ===")
        await extractor.analyze_repository(repo_url)
        
        # Direct graph queries to verify some data
        print("\\n=== Verifying Neo4j Data ===")
        
        # Check what classes are in intelligent_chunker
        results = await extractor.search_graph("classes_in_file", file_path="src/chunking/intelligent_chunker.py")
        print(f"\\nClasses found in intelligent_chunker.py: {len(results)}")
        for result in results:
            print(f"- {result['class_name']}")
        
        # Check a specific class's methods
        results = await extractor.search_graph("methods_of_class", class_name="IntelligentChunker")
        print(f"\\nMethods found in IntelligentChunker: {len(results)}")
        for result in results:
            print(f"- {result['method_name']}({', '.join(result['args'])})")
        
    except Exception as e:
        print(f"\\n❌ Error during execution: {e}")
        sys.exit(1)
    finally:
        await extractor.close()
        print("\\n✅ Test completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
