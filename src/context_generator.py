import os
from typing import Optional
import httpx

class BaseContextGenerator:
    def generate_code_example_title(self, code: str, context_before: str, context_after: str) -> str:
        raise NotImplementedError

class GeminiContextGenerator(BaseContextGenerator):
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        from google import genai
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
            
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name

    def generate_code_example_title(self, code: str, context_before: str, context_after: str) -> str:
        prompt = self._build_prompt(code, context_before, context_after)
        try:
            from google import genai
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
            print(f"Error generating code example summary via Gemini: {e}")
            return "Code Snippet"

    def _build_prompt(self, code: str, context_before: str, context_after: str) -> str:
        return f"""<context_before>
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

class InhouseContextGenerator(BaseContextGenerator):
    def __init__(self):
        # Defaulting to standard OpenAI-compatible completions endpoint path
        self.base_url = os.getenv("INHOUSE_LLM_BASE_URL", "http://localhost:8000/api/openai/v1").rstrip("/")
        self.api_key = os.getenv("INHOUSE_LLM_API_KEY", "")
        self.model_name = os.getenv("INHOUSE_LLM_MODEL", "mistral")

    def generate_code_example_title(self, code: str, context_before: str, context_after: str) -> str:
        prompt = self._build_prompt(code, context_before, context_after)
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_completion_tokens": 100
        }
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/chat/completions", 
                    headers=headers, 
                    json=payload, 
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                # Check for standard OpenAI response
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"].strip()
                # Check for direct 'message' fallback as per provided OpenAPI schema screenshot
                elif "message" in data:
                     return data["message"].strip()
                else:
                     print(f"Unexpected response format from in-house LLM: {data}")
                     return "Code Snippet"
                     
        except Exception as e:
            print(f"Error generating code example summary via In-house LLM: {e}")
            return "Code Snippet"

    def _build_prompt(self, code: str, context_before: str, context_after: str) -> str:
        return f"""<context_before>
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

class ContextGenerator:
    """
    Factory Router. Abstracts away summarization operations utilizing internal Providers mapping dynamically 
    to handle Contextual Retrieval snippet titles.
    """
    def __init__(self):
        provider_type = os.getenv("LLM_PROVIDER", "GEMINI").upper()
        
        if provider_type == "INHOUSE":
            print(f"Initializing In-House Context Generator at {os.getenv('INHOUSE_LLM_BASE_URL')}")
            self._provider = InhouseContextGenerator()
        else:
            print("Initializing standard Gemini Context Generator")
            self._provider = GeminiContextGenerator()

    def generate_code_example_title(self, code: str, context_before: str, context_after: str) -> str:
        return self._provider.generate_code_example_title(code, context_before, context_after)
