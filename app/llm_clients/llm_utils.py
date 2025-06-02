"""
Utility functions for LLM interactions
"""
from typing import Dict, Any, List, Optional, Union
from .gemini_client import gemini_client
from ..utils.logger import log_info, log_error

def generate_text(prompt: str, temperature: float = 0.7) -> str:
    """Generate text from a prompt"""
    try:
        # Create a new client with the specified temperature
        client = gemini_client
        client._temperature = temperature
        
        # Generate text
        return client.generate_text(prompt)
    except Exception as e:
        log_error(f"Error in generate_text: {str(e)}")
        return f"Error: {str(e)}"

def generate_chat_response(messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
    """Generate response from chat messages"""
    try:
        # Create a new client with the specified temperature
        client = gemini_client
        client._temperature = temperature
        
        # Generate response
        return client.generate_chat_response(messages)
    except Exception as e:
        log_error(f"Error in generate_chat_response: {str(e)}")
        return f"Error: {str(e)}"

def classify_text(text: str, categories: List[str]) -> str:
    """Classify text into one of the given categories"""
    try:
        return gemini_client.classify_text(text, categories)
    except Exception as e:
        log_error(f"Error in classify_text: {str(e)}")
        return categories[0]  # Default to first category on error

def extract_entities(text: str, entity_types: List[str]) -> Dict[str, List[str]]:
    """Extract entities from text"""
    try:
        return gemini_client.extract_entities(text, entity_types)
    except Exception as e:
        log_error(f"Error in extract_entities: {str(e)}")
        return {entity_type: [] for entity_type in entity_types}

def summarize_text(text: str, max_length: int = 200) -> str:
    """Summarize text"""
    try:
        return gemini_client.summarize_text(text, max_length)
    except Exception as e:
        log_error(f"Error in summarize_text: {str(e)}")
        return text[:max_length] + "..."  # Fallback to simple truncation

def analyze_sentiment(text: str) -> str:
    """Analyze sentiment of text"""
    try:
        return classify_text(text, ["positive", "neutral", "negative"])
    except Exception as e:
        log_error(f"Error in analyze_sentiment: {str(e)}")
        return "neutral"

def extract_keywords(text: str, max_keywords: int = 5) -> List[str]:
    """Extract keywords from text"""
    try:
        prompt = f"""Trích xuất tối đa {max_keywords} từ khóa quan trọng từ văn bản sau:
        
        {text}
        
        Trả về danh sách các từ khóa, mỗi từ khóa trên một dòng."""
        
        response = gemini_client.generate_text(prompt)
        
        # Parse response
        keywords = [keyword.strip() for keyword in response.split('\n') if keyword.strip()]
        return keywords[:max_keywords]
    except Exception as e:
        log_error(f"Error in extract_keywords: {str(e)}")
        return []

def translate_text(text: str, target_language: str = "vi") -> str:
    """Translate text to target language"""
    try:
        language_map = {
            "vi": "Vietnamese",
            "en": "English",
            "fr": "French",
            "de": "German",
            "es": "Spanish",
            "it": "Italian",
            "ja": "Japanese",
            "ko": "Korean",
            "zh": "Chinese"
        }
        
        language = language_map.get(target_language, target_language)
        
        prompt = f"""Translate the following text to {language}:
        
        {text}
        
        Translation:"""
        
        return gemini_client.generate_text(prompt)
    except Exception as e:
        log_error(f"Error in translate_text: {str(e)}")
        return text
