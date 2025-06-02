"""
Module for enhancing queries with context from chat history
"""
from typing import Dict, Any, List
from abc import ABC, abstractmethod
from ...utils.logger import log_info, log_error

class QueryEnhancer(ABC):
    """Abstract class for query enhancer"""
    
    @abstractmethod
    def enhance_query(self, query: str, context: Dict[str, Any]) -> str:
        """
        Enhance query with context
        
        Args:
            query (str): Original query
            context (Dict[str, Any]): Context extracted from chat history
            
        Returns:
            str: Enhanced query
        """
        pass
    
    @abstractmethod
    def detect_references(self, query: str) -> bool:
        """
        Detect if query contains references to previous conversation
        
        Args:
            query (str): Query to check
            
        Returns:
            bool: True if query contains references, False otherwise
        """
        pass

class DefaultQueryEnhancer(QueryEnhancer):
    """Default implementation of query enhancer"""
    
    def enhance_query(self, query: str, context: Dict[str, Any]) -> str:
        """
        Enhance query with context
        
        Args:
            query (str): Original query
            context (Dict[str, Any]): Context extracted from chat history
            
        Returns:
            str: Enhanced query
        """
        if not context:
            return query
        
        # Create context parts
        context_parts = []
        
        # Add mentioned products
        if 'mentioned_products' in context and context['mentioned_products']:
            products = ', '.join(context['mentioned_products'])
            context_parts.append(f"sản phẩm: {products}")
        
        # Add mentioned categories
        if 'mentioned_categories' in context and context['mentioned_categories']:
            categories = ', '.join(context['mentioned_categories'])
            context_parts.append(f"danh mục: {categories}")
        
        # Add preferences
        if 'preferences' in context and context['preferences']:
            preferences = ', '.join(context['preferences'])
            context_parts.append(f"sở thích: {preferences}")
        
        # Add price requirements
        if 'price_requirements' in context and context['price_requirements']:
            context_parts.append(f"yêu cầu giá: {context['price_requirements']}")
        
        # Add recent references
        if 'recent_references' in context and context['recent_references']:
            context_parts.append(f"tham chiếu gần đây: {context['recent_references']}")
        
        # Create enhanced query with context
        if context_parts:
            context_str = '; '.join(context_parts)
            enhanced_query = f"{query} (Ngữ cảnh từ cuộc trò chuyện trước: {context_str})"
            log_info(f"Enhanced query with context: {enhanced_query}")
            return enhanced_query
        
        return query
    
    def detect_references(self, query: str) -> bool:
        """
        Detect if query contains references to previous conversation
        
        Args:
            query (str): Query to check
            
        Returns:
            bool: True if query contains references, False otherwise
        """
        reference_keywords = [
            'này', 'đó', 'kia', 'vừa nói', 'vừa đề cập', 'tương tự', 'giống vậy', 'như vậy',
            'vừa rồi', 'trước đó', 'đã nói', 'đã đề cập', 'như trên', 'như đã nói',
            'loại đó', 'cái đó', 'sản phẩm đó', 'danh mục đó'
        ]
        
        has_reference = any(keyword in query.lower() for keyword in reference_keywords)
        
        if has_reference:
            log_info(f"Detected reference in query: {query}")
        
        return has_reference
    
    def enhance_query_with_products(self, query: str, products: List[str]) -> str:
        """
        Enhance query with specific products
        
        Args:
            query (str): Original query
            products (List[str]): List of product names
            
        Returns:
            str: Enhanced query
        """
        if not products:
            return query
        
        # Check if query contains reference keywords
        if self.detect_references(query):
            products_str = ', '.join(products)
            enhanced_query = f"{query} (Đang đề cập đến sản phẩm: {products_str})"
            log_info(f"Enhanced query with products: {enhanced_query}")
            return enhanced_query
        
        return query

# Default query enhancer implementation
query_enhancer = DefaultQueryEnhancer()
