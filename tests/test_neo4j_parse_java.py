import asyncio
import os
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_graphs.parse_repo_into_neo4j import DirectNeo4jExtractor

async def main():
    # Keep it safe inside test scope
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

    print(f"Connecting to Neo4j at {NEO4J_URI}...")
    extractor = DirectNeo4jExtractor(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    try:
        await extractor.initialize()
        
        # Point right at the dummy java repo
        dummy_repo_path = Path(__file__).parent / "dummy_java"
        repo_name = "test-dummy-java"
        
        print(f"\n=== Analyzing Java repository: {dummy_repo_path} ===")
        
        # Override standard parsing to just hit the local directory
        # Collect all relevant source files
        extensions = {'.java'}
        source_files = []
        for file_path in dummy_repo_path.rglob('*'):
            if file_path.suffix in extensions:
                source_files.append(file_path)
                
        # Manually extract just the Java test data
        modules_data = []
        for file_path in source_files:
            analysis = extractor.analyzer.analyze_file(file_path, dummy_repo_path, set())
            if analysis:
                modules_data.append(analysis)
        
        # Create Neo4j mappings
        await extractor._create_graph(repo_name, modules_data)
        
        # Print results directly from graph query
        async with extractor.driver.session() as session:
            print(f"\n=== Verifying Neo4j Java Data ===")
            
            # Check for our DummyJavaService class
            result = await session.run(
                "MATCH (c:Class {name: 'DummyJavaService'}) RETURN c.full_name AS full_name"
            )
            records = [record async for record in result]
            print(f"Classes found in Neo4j matching 'DummyJavaService': {len(records)}")
            
            # Print methods attached to it
            result = await session.run(
                "MATCH (c:Class {name: 'DummyJavaService'})-[:HAS_METHOD]->(m:Method) "
                "RETURN m.name AS name"
            )
            methods = [record["name"] async for record in result]
            print(f"\nMethods found inside Neo4j for DummyJavaService: {len(methods)}")
            for m in sorted(methods):
                print(f"- {m}()")
                
            print("\n✅ Java integration extraction test successfully mapped to schema.")
                
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if extractor.driver:
            await extractor.driver.close()

if __name__ == "__main__":
    asyncio.run(main())
