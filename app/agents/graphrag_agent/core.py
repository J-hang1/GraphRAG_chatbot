"""
Core functionality for GraphRAG agent.

This module provides the main functionality for the GraphRAG agent, including:
- Intent extraction and analysis
- Query generation and execution
- Result processing and formatting
- Hybrid search functionality
- Core utility functions
"""
from typing import Dict, Any, List, Optional, Union, Set, Tuple
import json
import logging
import os
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from sklearn.metrics.pairwise import cosine_similarity

from app.utils.logger import log_info, log_error
from app.neo4j_client.connection import execute_query
from app.config.phobert_config import PHOBERT_MODEL_PATH, PHOBERT_MODEL_NAME
from ..core.constants import ERROR_MESSAGES, SUCCESS_MESSAGES
from ..core.core_functions import compute_entity_semantic_similarity, get_phobert_manager

from .statistical_queries import generate_statistical_cypher_query, is_statistical_query,aggregate_results_by_category_and_product, format_statistics_for_response
from .semantic_entity_matching import SemanticEntityMatching
from .cypher_generator import CypherGenerator

@dataclass
class IntentData:
    """Data class for storing intent information"""
    intent_type: str
    intent_text: str
    product_names: Dict[str, List[str]]
    category_names: List[str]
    filters: Dict[str, Any]
    is_store_query: bool
    is_order_query: bool
    confidence: float
    entities: Dict[str, Any]
    keywords: List[str]
    target_customers: List[str]

class GraphRAGCore:
    """Core functionality for GraphRAG agent.
    
    This class handles the main operations of the GraphRAG agent including:
    - Intent extraction and analysis
    - Query generation and execution
    - Result processing and formatting
    
    Attributes:
        _logger: Logger instance for the class
        _semantic_matcher: Instance of SemanticEntityMatching for entity matching
        _cypher_generator: Instance of CypherGenerator for query generation
    """
    
    def __init__(self):
        """Initialize GraphRAGCore with required components."""
        self._logger = logging.getLogger('agent.graphrag.core')
        self._semantic_matcher = SemanticEntityMatching()
        self._cypher_generator = CypherGenerator()
        
    def extract_intent_data(self, intent_text: str, original_query: Optional[str] = None) -> Dict[str, Any]:
        """Extract intent data from text.
        
        Args:
            intent_text: The text to extract intent from
            original_query: Optional original query text
            
        Returns:
            Dict containing extracted intent data
            
        Raises:
            ValueError: If intent_text is empty
        """
        if not intent_text:
            raise ValueError("intent_text cannot be empty")
            
        log_info(f"Extracting intent_data from intent_text: {intent_text}")

        # Use intent_text if original_query is None
        original_query = original_query or intent_text

        # Extract entities from intent_text
        from ..recommend_agent.entity_extraction import extract_entities
        entities = extract_entities(original_query)
        log_info(f"Extracted entities: {json.dumps(entities, ensure_ascii=False)}")

        # Initialize intent_data with default values
        intent_data = self._create_base_intent_data(intent_text, entities)
        
        # Add entity information
        self._enrich_intent_data(intent_data, entities)

        log_info(f"Intent data extraction result: {json.dumps(intent_data, ensure_ascii=False)}")
        return intent_data
        
    def _create_base_intent_data(self, intent_text: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Create base intent data structure.
        
        Args:
            intent_text: The text to create intent data for
            entities: Dictionary of extracted entities
            
        Returns:
            Dict containing base intent data structure
        """
        combined_keywords = list(set(entities.get("entities", []) + entities.get("keywords", [])))
        
        return {
            "intent_type": "search",
            "intent_text": intent_text,
            "product_names": {"vi": [], "en": []},
            "category_names": [],
            "filters": {},
            "is_store_query": entities.get("store_info", False),
            "is_order_query": entities.get("order_info", False),
            "confidence": 1.0,
            "entities": entities,
            "keywords": combined_keywords,
            "target_customers": entities.get("target_audience", [])
        }
        
    def _enrich_intent_data(self, intent_data: Dict[str, Any], entities: Dict[str, Any]) -> None:
        """Enrich intent data with entity information.
        
        Args:
            intent_data: The intent data to enrich
            entities: Dictionary of extracted entities
        """
        # Add product names
        if entities.get("entities", []):
            for entity in entities["entities"]:
                if entity not in intent_data["product_names"]["vi"]:
                    intent_data["product_names"]["vi"].append(entity)

        # Add product attributes
        if entities.get("product_attributes", {}):
            intent_data["filters"].update(entities["product_attributes"])

        # Add constraints
        if entities.get("constraints", {}):
            intent_data["filters"].update(entities["constraints"])
        
    def is_store_or_order_query(self, message: str) -> bool:
        """Check if query is about store or order.
        
        Args:
            message: The message to check
            
        Returns:
            bool indicating if query is about store or order
        """
        store_keywords = {
            'cửa hàng', 'store', 'chi nhánh', 'branch', 'location', 
            'địa chỉ', 'địa điểm', 'vị trí', 'mở cửa', 'đóng cửa',
            'giờ mở cửa', 'giờ đóng cửa', 'thời gian mở cửa', 
            'thời gian hoạt động', 'gần đây', 'gần nhất', 'address',
            'opening hours'
        }
        
        order_keywords = {
            'đơn hàng', 'order', 'lịch sử mua hàng', 'purchase history',
            'đặt hàng', 'mua hàng', 'thanh toán', 'giao hàng', 'vận chuyển',
            'đã đặt', 'đã mua', 'lịch sử', 'lịch sử đơn hàng', 'purchase',
            'delivery', 'shipping', 'payment', 'history'
        }

        message_lower = message.lower()
        return any(keyword in message_lower for keyword in store_keywords | order_keywords)
        
    def generate_query(self, intent_data: Dict[str, Any]) -> str:
        """Generate appropriate query based on intent data.
        
        Args:
            intent_data: Dictionary containing intent information
            
        Returns:
            str containing the generated Cypher query
            
        Raises:
            ValueError: If intent_data is invalid
        """
        if not intent_data:
            raise ValueError("intent_data cannot be empty")
            
        if intent_data.get('is_store_query'):
            return self.generate_store_query(intent_data)
        elif intent_data.get('is_order_query'):
            return self.generate_order_query(intent_data)
        else:
            return self.generate_product_query(intent_data)
        
    def generate_store_query(self, intent_data: Dict[str, Any]) -> str:
        """Generate store query.
        
        Args:
            intent_data: Dictionary containing intent information
            
        Returns:
            str containing the generated store query
        """
        intent_text = intent_data.get("intent_text", "").lower()
        keywords = intent_data.get("keywords", [])

        log_info(f"Generating store query for: '{intent_text}'")
        log_info(f"Keywords: {keywords}")

        # Check store query type
        if any(keyword in intent_text for keyword in ["mở cửa muộn nhất", "muộn nhất", "đóng cửa muộn nhất"]):
            return self._generate_latest_closing_store_query()
            
        # Default return all stores
        return """
        MATCH (s:store)
        RETURN s
        """
        
    def _generate_latest_closing_store_query(self) -> str:
        """Generate query for finding store with latest closing time.
        
        Returns:
            str containing the generated query
        """
        return """
        MATCH (s:store)
        WHERE s.open_close IS NOT NULL
        WITH s, split(s.open_close, ' - ')[1] as close_time
        WHERE close_time IS NOT NULL
        WITH s, close_time,
             CASE
               WHEN close_time CONTAINS ':' THEN
                 toInteger(split(close_time, ':')[0]) * 60 + toInteger(split(close_time, ':')[1])
               ELSE 999999
             END as close_minutes
        WITH MAX(close_minutes) as max_close_minutes
        MATCH (s:store)
        WHERE s.open_close IS NOT NULL
        WITH s, split(s.open_close, ' - ')[1] as close_time, max_close_minutes
        WHERE close_time IS NOT NULL
        WITH s, close_time, max_close_minutes,
             CASE
               WHEN close_time CONTAINS ':' THEN
                 toInteger(split(close_time, ':')[0]) * 60 + toInteger(split(close_time, ':')[1])
               ELSE 999999
             END as close_minutes
        WHERE close_minutes = max_close_minutes
        RETURN s
        """
        
    def generate_order_query(self, intent_data: Dict[str, Any]) -> str:
        """Generate order query.
        
        Args:
            intent_data: Dictionary containing intent information
            
        Returns:
            str containing the generated order query
        """
        return self._cypher_generator.generate_order_query(intent_data)
        
    def generate_product_query(self, intent_data: Dict[str, Any]) -> str:
        """Generate product query.
        
        Args:
            intent_data: Dictionary containing intent information
            
        Returns:
            str containing the generated product query
        """
        if is_statistical_query(intent_data):
            return generate_statistical_cypher_query(intent_data)
        return self._cypher_generator.generate_product_query(intent_data)
        
    def execute_query(self, query: str) -> List[Dict]:
        """Execute Cypher query.
        
        Args:
            query: The Cypher query to execute
            
        Returns:
            List of dictionaries containing query results
            
        Raises:
            Exception: If query execution fails
        """
        try:
            return execute_query(query)
        except Exception as e:
            self._logger.error(f"Error executing query: {str(e)}")
            raise
            
    def process_results(self, results: List[Dict], intent_data: Dict[str, Any]) -> List[Dict]:
        """Process query results.
        
        Args:
            results: List of dictionaries containing query results
            intent_data: Dictionary containing intent information
            
        Returns:
            List of processed results
            
        Raises:
            Exception: If result processing fails
        """
        try:
            if is_statistical_query(intent_data):
                return format_statistics_for_response(
                    aggregate_results_by_category_and_product(results)
                )
            return results
        except Exception as e:
            self._logger.error(f"Error processing results: {str(e)}")
            raise 

def load_product_communities() -> Dict[str, Any]:
    """Load all product communities from Neo4j"""
    log_info("📥 Loading product communities...")

    query = """
    MATCH (pc:ProductCommunity)
    RETURN pc.id AS id,
           pc.name AS name,
           pc.common_features AS common_features,
           pc.differences AS differences,
           pc.variant_relationships AS variant_relationships,
           pc.target_customers AS target_customers,
           pc.marketing_suggestions AS marketing_suggestions,
           pc.faq AS faq,
           pc.keywords AS keywords,
           pc.embedding AS embedding
    """
    result = execute_query(query)

    product_communities = {}
    for record in result:
        community_id = record.get("id")
        if community_id is None or (isinstance(community_id, str) and not community_id.strip()):
            continue

        # Process keywords
        keywords = record.get("keywords", [])
        if isinstance(keywords, str):
            try:
                keywords = json.loads(keywords)
            except:
                keywords = [keywords]

        # Process FAQ
        faq = record.get("faq", [])
        if isinstance(faq, str):
            try:
                faq = json.loads(faq)
            except:
                faq = []

        # Process embedding
        embedding = record.get("embedding")
        if isinstance(embedding, str):
            try:
                embedding = json.loads(embedding)
            except:
                embedding = None

        product_communities[community_id] = {
            "id": community_id,
            "name": record.get("name", ""),
            "common_features": record.get("common_features", ""),
            "differences": record.get("differences", ""),
            "variant_relationships": record.get("variant_relationships", ""),
            "target_customers": record.get("target_customers", ""),
            "marketing_suggestions": record.get("marketing_suggestions", ""),
            "faq": faq,
            "keywords": keywords,
            "embedding": embedding
        }

        # Get products in community
        products_query = """
        MATCH (pc:ProductCommunity)-[:CONTAINS_PRODUCT]->(p:Product)
        WHERE pc.id = $community_id
        RETURN p.id AS id, p.name AS name, p.descriptions AS description
        """
        products_result = execute_query(products_query, {"community_id": community_id})

        products = []
        for product_record in products_result:
            products.append({
                "id": product_record.get("id"),
                "name": product_record.get("name", ""),
                "description": product_record.get("description", "")
            })

        product_communities[community_id]["products"] = products

    log_info(f"✅ Loaded {len(product_communities)} product communities")
    return product_communities

def create_community_text(community_data: Dict[str, Any]) -> str:
    """Create text representation of community data"""
    text_parts = []
    
    if community_data.get("name"):
        text_parts.append(f"Name: {community_data['name']}")
        
    if community_data.get("common_features"):
        text_parts.append(f"Common features: {community_data['common_features']}")
        
    if community_data.get("differences"):
        text_parts.append(f"Differences: {community_data['differences']}")
        
    if community_data.get("target_customers"):
        text_parts.append(f"Target customers: {community_data['target_customers']}")
        
    if community_data.get("keywords"):
        keywords = community_data["keywords"]
        if isinstance(keywords, list):
            keywords = ", ".join(keywords)
        text_parts.append(f"Keywords: {keywords}")
        
    return " | ".join(text_parts) 