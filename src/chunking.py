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
                chunk = text[start:].strip()
                if chunk:
                    chunks.append(chunk)
                break

            # Slicing the provisional window
            window = text[start:end]
            
            # --- Splitting Priority 1: Prevent severing code blocks ---
            # Try to find a code block boundary (```) searching backwards
            split_idx = window.rfind('```')
            if split_idx != -1 and split_idx > safe_chunk_size * 0.3:
                end = start + split_idx
            else:
                # --- Splitting Priority 2: Paragraph Breaks (\n\n) ---
                split_idx = window.rfind('\n\n')
                if split_idx != -1 and split_idx > safe_chunk_size * 0.3:
                    end = start + split_idx
                else:
                    # --- Splitting Priority 3: Sentence Breaks (. ) ---
                    split_idx = window.rfind('. ')
                    if split_idx != -1 and split_idx > safe_chunk_size * 0.3:
                        end = start + split_idx + 1 # Include the period
                    else:
                        # --- Splitting Priority 4: Line Breaks (\n) (Crucial for code blocks) ---
                        split_idx = window.rfind('\n')
                        if split_idx != -1 and split_idx > safe_chunk_size * 0.3:
                            end = start + split_idx
                        else:
                            # --- Splitting Priority 5: Space Breaks ( ) ---
                            split_idx = window.rfind(' ')
                            if split_idx != -1 and split_idx > safe_chunk_size * 0.1:
                                end = start + split_idx

            # Extract the refined chunk and clean whitespace
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position forward
            start = end

        return chunks

def extract_code_blocks(markdown_content: str, min_length: int = 50) -> List[dict]:
    """
    Extracts isolated ```` code blocks from a markdown document.
    Returns a list of dictionaries containing the code, language, and the 
    surrounding 500 characters of prose context.
    """
    code_blocks = []
    content = markdown_content.strip()
    
    # Handle edge case where the document starts directly with a code block
    start_offset = 3 if content.startswith('```') else 0
    
    # Find all occurrences of triple backticks
    backtick_positions = []
    pos = start_offset
    while True:
        pos = markdown_content.find('```', pos)
        if pos == -1:
            break
        backtick_positions.append(pos)
        pos += 3
        
    # Process pairs of backticks to extract blocks
    i = 0
    while i < len(backtick_positions) - 1:
        start_pos = backtick_positions[i]
        end_pos = backtick_positions[i + 1]
        
        # Raw block content
        code_section = markdown_content[start_pos+3:end_pos]
        
        # Extract language specifier if present
        lines = code_section.split('\n', 1)
        if len(lines) > 1 and lines[0].strip() and ' ' not in lines[0].strip() and len(lines[0].strip()) < 20:
            language = lines[0].strip()
            code_content = lines[1].strip()
        else:
            language = ""
            code_content = code_section.strip()
            
        # Ignore extremely tiny snippets
        if len(code_content) < min_length:
            i += 2
            continue
            
        # Extract surrounding context (500 chars before and after)
        context_start = max(0, start_pos - 500)
        context_before = markdown_content[context_start:start_pos].strip()
        
        context_end = min(len(markdown_content), end_pos + 3 + 500)
        context_after = markdown_content[end_pos + 3:context_end].strip()
        
        code_blocks.append({
            'code': code_content,
            'language': language,
            'context_before': context_before,
            'context_after': context_after
        })
        
        i += 2
        
    return code_blocks
