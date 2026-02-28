import os
import sys

# Add the src directory to the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from neo4j import GraphDatabase

def test_connection():
    uri = os.environ.get('NEO4J_URI', 'bolt://neo4j:7687')
    user = os.environ.get('NEO4J_USER', 'neo4j')
    password = os.environ.get('NEO4J_PASSWORD', 'password')

    print(f"Attempting to connect to Neo4j at {uri} with user {user}...")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        print("✅ Successfully connected to Neo4j container!")
        driver.close()
    except Exception as e:
        print("❌ Failed to connect to Neo4j:")
        print(str(e))
        sys.exit(1)

if __name__ == "__main__":
    test_connection()
