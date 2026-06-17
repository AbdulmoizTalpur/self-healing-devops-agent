import os
import json
import requests
from typing import Type, TypeVar, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types
from agent.config import Config

T = TypeVar('T', bound=BaseModel)

class LLMClient:
    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or Config.LLM_PROVIDER).lower()
        self.gemini_key = Config.GEMINI_API_KEY
        self.openai_key = Config.OPENAI_API_KEY
        
        # Initialize Google GenAI Client if using Gemini and API key is present and not mock
        self.gemini_client = None
        if self.provider == "gemini" and self.gemini_key and "mock" not in self.gemini_key.lower():
            self.gemini_client = genai.Client(api_key=self.gemini_key)

    @property
    def is_mock(self) -> bool:
        """Returns True if the client is configured to run in mock/simulation mode."""
        if self.provider == "gemini":
            return not self.gemini_key or "mock" in self.gemini_key.lower()
        elif self.provider in ("openai", "openrouter"):
            return not self.openai_key or "mock" in self.openai_key.lower()
        return True

    def generate_content(self, prompt: str, response_schema: Optional[Type[T]] = None, temperature: float = 0.1) -> str:
        """
        Generate raw content from the configured LLM provider.
        If response_schema is provided, requests JSON matching the schema.
        """
        if self.is_mock:
            return "mock"

        if self.provider == "gemini":
            if not self.gemini_client:
                raise ValueError("Gemini client is not initialized (missing or invalid API key).")
            
            config = types.GenerateContentConfig(temperature=temperature)
            if response_schema:
                config.response_mime_type = "application/json"
                config.response_schema = response_schema
                
            response = self.gemini_client.models.generate_content(
                model=Config.GEMINI_MODEL,
                contents=prompt,
                config=config
            )
            return response.text.strip()
            
        elif self.provider in ("openai", "openrouter"):
            if not self.openai_key:
                raise ValueError(f"{self.provider.upper()} API key is not configured.")
                
            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": Config.OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature
            }
            
            # If response_schema is requested, instruct the model and request JSON mode
            if response_schema:
                schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
                enhanced_prompt = (
                    f"{prompt}\n\n"
                    f"CRITICAL: You MUST return a JSON object that adheres strictly to the following JSON schema:\n"
                    f"{schema_json}\n\n"
                    f"Return ONLY valid JSON. Do not include any explanations, markdown code blocks, or comments."
                )
                payload["messages"] = [{"role": "user", "content": enhanced_prompt}]
                payload["response_format"] = {"type": "json_object"}
                
            try:
                response = requests.post(
                    f"{Config.OPENAI_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=90
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return content.strip()
            except Exception as e:
                # Retrieve verbose error from response if available
                error_msg = str(e)
                try:
                    if 'response' in locals() and response.text:
                        error_msg = f"{e} - API Response: {response.text}"
                except Exception:
                    pass
                raise RuntimeError(f"HTTP request to {self.provider.upper()} API failed: {error_msg}")
                
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def generate_structured(self, prompt: str, response_schema: Type[T], temperature: float = 0.1) -> T:
        """Generate content and parse it directly into the target Pydantic schema."""
        raw_text = self.generate_content(prompt, response_schema=response_schema, temperature=temperature)
        if raw_text == "mock":
            raise ValueError("Mock mode detected; use mock handler instead.")
            
        clean_text = raw_text.strip()
        
        # If response contains markdown blocks (e.g. ```json ... ```), strip them
        if clean_text.startswith("```"):
            lines = clean_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean_text = "\n".join(lines).strip()
            
        return response_schema.model_validate_json(clean_text)
