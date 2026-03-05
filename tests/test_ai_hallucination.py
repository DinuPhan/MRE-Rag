import os
import sys
import asyncio
from pathlib import Path

# Add the src and knowledge_graphs directory to the python path
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, src_dir)
sys.path.insert(0, os.path.join(src_dir, 'knowledge_graphs'))

from knowledge_graphs.ai_hallucination_detector import AIHallucinationDetector
import logging

# Configure basic logging for the script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def main():
    """Test the AI Hallucination Detector against a mock script."""
    
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
    neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')
    
    print(f"Connecting to Neo4j at {neo4j_uri}...")
    detector = AIHallucinationDetector(neo4j_uri, neo4j_user, neo4j_password)
    
    script_path = os.path.join(os.path.dirname(__file__), "mock_ai_script.py")
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    
    try:
        await detector.initialize()
        
        print(f"\\n=== Analyzing AI script: {script_path} ===")
        await detector.detect_hallucinations(
            script_path=script_path,
            output_dir=output_dir,
            save_json=True,
            save_markdown=True,
            print_summary=True
        )
        
        print(f"\\nArtifacts saved to: {output_dir}")
        
    except Exception as e:
        print(f"\\n❌ Error during execution: {e}")
        sys.exit(1)
    finally:
        print("\\n✅ Test completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
