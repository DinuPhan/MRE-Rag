import re
from typing import List

class IntelligentChunker:
    """
    Intelligently splits Markdown text into chunks based on semantic headers.
    It tracks code blocks to avoid splitting on `# comment` lines in code.
    If a semantic section exceeds `chunk_size`, it uses a reverse-lookup 
    heuristic to elegantly split on ````, `\n\n`, or `. ` boundaries.
    """
    def __init__(self, chunk_size: int = 1500):
        self.chunk_size = chunk_size

    def chunk_text(self, text: str) -> List[str]:
        if not text:
            return []

        chunks: List[str] = []
        lines = text.split('\n')
        
        current_section = []
        current_header = ""
        in_code_block = False

        for line in lines:
            # Toggle code block state when we see triple backticks
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                current_section.append(line)
                continue

            # Check if this line is a header (and we are NOT in a code block)
            header_match = re.match(r"^(#{1,6})\s+(.*)$", line)
            
            if not in_code_block and header_match:
                # We found a new semantic section boundary!
                
                # 1. Save the previous section if it has content
                section_text = '\n'.join(current_section).strip()
                if section_text:
                    self._process_section(section_text, current_header, chunks)
                
                # 2. Start tracking the new section
                current_header = line.strip()
                current_section = [line]
            else:
                # Regular line, just append it
                current_section.append(line)

        # Process the final trailing section
        final_text = '\n'.join(current_section).strip()
        if final_text:
            self._process_section(final_text, current_header, chunks)

        return chunks

    def _process_section(self, section_text: str, current_header: str, chunks_output: List[str]):
        """
        Determines if a section fits within chunk_size. If it does, we append it.
        If it's oversized, we send it to the smart splitting fallback algorithm.
        """
        if len(section_text) <= self.chunk_size:
            # It fits perfectly!
            chunks_output.append(section_text)
        else:
            # It's too large. We need to split it using the reverse-lookup algorithm,
            # injecting the parent header context into all split pieces.
            
            # If there's a header, we need to artificially inject it into subsequent chunks
            # so we subtract its length from our available budget.
            header_prefix = f"{current_header}\n" if current_header else ""
            
            sub_chunks = self._smart_split(section_text, current_header)
            
            for i, chunk in enumerate(sub_chunks):
                # Only the first chunk contains the native header. Subsequent ones need injection.
                if i > 0 and current_header and not chunk.startswith(current_header):
                    chunks_output.append(f"{header_prefix}{chunk}")
                else:
                    chunks_output.append(chunk)

    def _smart_split(self, text: str, context_header: str) -> List[str]:
        """
        Splits text into chunks, respecting code blocks, paragraphs, and sentences.
        (Adapted from references/src/crawl4ai_mcp.py logic)
        """
        chunks = []
        start = 0
        text_length = len(text)
        
        # Determine strict budget limit for the actual body content
        header_prefix = f"{context_header}\n" if context_header else ""
        safe_chunk_size = self.chunk_size - len(header_prefix)
        if safe_chunk_size <= 0:
            safe_chunk_size = self.chunk_size # Fallback edge case for absurdly long headers

        while start < text_length:
            # Calculate provisional end position
            end = start + safe_chunk_size

            # If we're at the end of the text, take what's left
            if end >= text_length:
                chunks.append(text[start:].strip())
                break

            # Slicing the provisional window
            window = text[start:end]
            
            # --- Splitting Priority 1: Prevent severing code blocks ---
            # Try to find a code block boundary (```) searching backwards
            split_idx = window.rfind('```')
            
            # Only break if it is decently far into the chunk (avoids micro-chunking)
            if split_idx != -1 and split_idx > safe_chunk_size * 0.3:
                # We want to keep the backticks cleanly inside ONE chunk.
                # If we slice right BEFORE the backticks, the code block is deferred entirely to the NEXT chunk.
                end = start + split_idx

            # --- Splitting Priority 2: Paragraph Breaks (\n\n) ---
            elif '\n\n' in window:
                split_idx = window.rfind('\n\n')
                if split_idx > safe_chunk_size * 0.3:
                    end = start + split_idx

            # --- Splitting Priority 3: Sentence Breaks (. ) ---
            elif '. ' in window:
                split_idx = window.rfind('. ')
                if split_idx > safe_chunk_size * 0.3:
                    end = start + split_idx + 1 # Include the period

            # Extract the refined chunk and clean whitespace
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position forward
            start = end

        return chunks
