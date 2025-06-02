"""
Gemini client for LLM interactions
"""
import os
import time
from typing import Dict, Any, List, Optional
from flask import current_app
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from ..utils.logger import log_info, log_error
from ..utils.llm_counter import llm_counter, count_llm_call
from dotenv import load_dotenv

# Tải biến môi trường từ .env
load_dotenv()

class GeminiClient:
    """Client for interacting with Gemini models"""

    def __init__(self, model_name: Optional[str] = None, temperature: float = 0.7):
        """Initialize Gemini client"""
        self._model = None
        self._model_name = model_name
        self._temperature = temperature

    @property
    def model(self):
        """Lazy load model instance"""
        if self._model is None:
            # Thử lấy từ Flask config trước, nếu không có thì lấy từ biến môi trường
            try:
                api_key = current_app.config.get('GOOGLE_API_KEY', os.getenv('GOOGLE_API_KEY'))
                model_name = self._model_name or current_app.config.get('LLM_MODEL', os.getenv('LLM_MODEL', 'gemini-1.5-flash-latest'))
            except RuntimeError:
                # Không có Flask context
                api_key = os.getenv('GOOGLE_API_KEY')
                model_name = self._model_name or os.getenv('LLM_MODEL', 'gemini-1.5-flash-latest')

            if not api_key:
                log_error("GOOGLE_API_KEY không được cấu hình")
                raise ValueError("GOOGLE_API_KEY không được cấu hình")

            os.environ["GOOGLE_API_KEY"] = api_key

            log_info(f"Khởi tạo Gemini model: {model_name} với temperature: {self._temperature}")

            self._model = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
                temperature=self._temperature,
                top_p=0.95,
                top_k=40,
                max_output_tokens=1024,
                retry_max_attempts=3
            )

        return self._model

    @count_llm_call
    def generate_text(self, prompt: str) -> str:
        """Generate text from a prompt"""
        try:
            response = self.model.invoke(prompt)
            return response.content
        except Exception as e:
            log_error(f"Error generating text: {str(e)}")
            return f"Error: {str(e)}"

    @count_llm_call
    def generate_chat_response(self, messages: List[Dict[str, str]]) -> str:
        """Generate response from chat messages"""
        try:
            # Convert messages to LangChain format
            langchain_messages = []
            for message in messages:
                if message['role'] == 'user':
                    langchain_messages.append(HumanMessage(content=message['content']))
                elif message['role'] == 'assistant':
                    langchain_messages.append(AIMessage(content=message['content']))

            # Generate response
            response = self.model.invoke(langchain_messages)
            return response.content
        except Exception as e:
            log_error(f"Error generating chat response: {str(e)}")
            return f"Error: {str(e)}"

    @count_llm_call
    def classify_text(self, text: str, categories: List[str]) -> str:
        """Classify text into one of the given categories"""
        try:
            prompt = f"""Phân loại văn bản sau vào một trong các danh mục: {', '.join(categories)}

            Văn bản: {text}

            Trả lời chỉ với một từ duy nhất là tên danh mục."""

            response = self.model.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            log_error(f"Error classifying text: {str(e)}")
            return categories[0]  # Default to first category on error

    @count_llm_call
    def extract_entities(self, text: str, entity_types: List[str]) -> Dict[str, List[str]]:
        """Extract entities from text"""
        try:
            prompt = f"""Trích xuất các thực thể sau từ văn bản: {', '.join(entity_types)}

            Văn bản: {text}

            Trả về kết quả theo định dạng JSON với các trường là tên thực thể và giá trị là danh sách các thực thể tìm thấy."""

            response = self.model.invoke(prompt)

            # Parse JSON response
            import json
            import re

            # Try to find JSON in the response
            json_match = re.search(r'```json\s*(.*?)\s*```', response.content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response.content

            # Clean up the string
            json_str = re.sub(r'```.*?```', '', json_str, flags=re.DOTALL)

            # Parse JSON
            try:
                entities = json.loads(json_str)
                return entities
            except:
                # Fallback to empty result
                return {entity_type: [] for entity_type in entity_types}

        except Exception as e:
            log_error(f"Error extracting entities: {str(e)}")
            return {entity_type: [] for entity_type in entity_types}

    @count_llm_call
    def summarize_text(self, text: str, max_length: int = 200) -> str:
        """Summarize text"""
        try:
            prompt = f"""Tóm tắt văn bản sau trong tối đa {max_length} ký tự:

            {text}

            Tóm tắt:"""

            response = self.model.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            log_error(f"Error summarizing text: {str(e)}")
            return text[:max_length] + "..."  # Fallback to simple truncation

# Singleton instance
gemini_client = GeminiClient()

def get_gemini_llm():
    """
    Get Gemini LLM instance

    Returns:
        ChatGoogleGenerativeAI: Gemini LLM instance
    """
    return gemini_client.model
