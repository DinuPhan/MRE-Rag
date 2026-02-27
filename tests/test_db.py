import os
from qdrant_client import QdrantClient
qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
client = QdrantClient(url=qdrant_url)
print("\n--- Collections in Qdrant ---")
for c in client.get_collections().collections:
    print(c.name)
    print("Example Document:")
    res = client.scroll(collection_name=c.name, limit=1)
    if res and res[0]:
        print(res[0][0].payload['content'][:150])
    print("-" * 20)
