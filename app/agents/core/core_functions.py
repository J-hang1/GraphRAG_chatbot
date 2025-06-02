"""
Core functions for semantic similarity and PhoBERT management
"""
from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import logging
from app.utils.logger import log_info, log_error
import re

def extract_comparison_value_from_text(text: str) -> Optional[float]:
    """
    Extract numeric comparison value from text.
    
    Args:
        text: Text containing numeric value
        
    Returns:
        Optional[float]: Extracted numeric value or None if not found
        
    Examples:
        >>> extract_comparison_value_from_text("giá dưới 30000")
        30000.0
        >>> extract_comparison_value_from_text("calo trên 100")
        100.0
        >>> extract_comparison_value_from_text("không có số")
        None
    """
    try:
        # Remove commas from numbers
        text = text.replace(',', '')
        
        # Try to find numbers in text
        numbers = re.findall(r'\d+(?:\.\d+)?', text)
        
        if numbers:
            # Convert first found number to float
            return float(numbers[0])
            
        return None
        
    except Exception as e:
        log_error(f"Error extracting comparison value from text: {str(e)}")
        return None

def compute_entity_semantic_similarity(text1: str, text2: str) -> float:
    """
    Compute semantic similarity between two texts using PhoBERT embeddings.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        float: Semantic similarity score between 0 and 1
    """
    try:
        # Get PhoBERT manager
        phobert_manager = get_phobert_manager()
        
        # Get embeddings
        embedding1 = phobert_manager.get_embedding(text1)
        embedding2 = phobert_manager.get_embedding(text2)
        
        if embedding1 is None or embedding2 is None:
            return 0.0
            
        # Compute cosine similarity
        similarity = np.dot(embedding1, embedding2) / (
            np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
        )
        
        return float(similarity)
        
    except Exception as e:
        log_error(f"Error computing semantic similarity: {str(e)}")
        return 0.0

def fallback_semantic_similarity(text1: str, text2: str) -> float:
    """Fallback method for computing semantic similarity"""
    return 0.5

def get_phobert_manager():
    """
    Get PhoBERT manager instance.
    
    Returns:
        PhoBERTManager: PhoBERT manager instance
    """
    try:
        return get_phobert_manager()
    except Exception as e:
        log_error(f"Error getting PhoBERT manager: {str(e)}")
        return None 