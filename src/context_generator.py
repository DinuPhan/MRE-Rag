import os
from google import genai

class ContextGenerator:
    """
    Optional AI-powered utility for Contextual Retrieval.
    Used to generate 1-sentence summaries/titles for isolated code snippets
    based on their surrounding prose, maximizing the semantic accuracy of 
    the snippet's embedding.
    """
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
            
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name

    def generate_code_example_title(self, code: str, context_before: str, context_after: str) -> str:
        """
        Generates a concise 1-sentence title/summary for a code snippet.
        """
        prompt = f"""<context_before>
{context_before[-500:] if len(context_before) > 500 else context_before}
</context_before>

<code_example>
{code[:1500] if len(code) > 1500 else code}
</code_example>

<context_after>
{context_after[:500] if len(context_after) > 500 else context_after}
</context_after>

Based on the code example and its surrounding context, provide a concise 1-sentence summary/title that describes what this code example demonstrates. Formulate it so it serves well as search metadata (e.g. 'Example demonstrating how to configure cache bypass in Crawl4AI'). Do NOT use Markdown formatting or quote marks.
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=100
                )
            )
            return response.text.strip()
        except Exception as e:
            print(f"Error generating code example summary: {e}")
            return "Code Snippet"
