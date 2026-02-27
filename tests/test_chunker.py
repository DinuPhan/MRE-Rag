import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.chunking import IntelligentChunker

text = """# Python Setup
Here is how you start the crawler.
```python
# This is a comment inside a code block! It should NOT be split!
from crawl4ai import AsyncWebCrawler
```

## Options
Here are some options.
""" * 5

chunker = IntelligentChunker(chunk_size=150)
chunks = chunker.chunk_text(text)
for i, c in enumerate(chunks):
    print(f"--- Chunk {i} ({len(c)} chars) ---")
    print(c)
