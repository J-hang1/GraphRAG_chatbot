"""
Cypher query generator for GraphRAG agent.

This module provides functionality to generate Cypher queries for different types of data:
- Product queries
- Category queries
- Store queries
"""
from typing import Dict, Any, List, Optional, Union, Set
import json
import logging
from dataclasses import dataclass
from ...utils.logger import log_info, log_error
from ..core.constants import QUERY_TEMPLATES

@dataclass
class QueryConditions:
    """Data class for storing query conditions"""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    sugar: Optional[float] = None
    caffeine: Optional[float] = None
    calories: Optional[float] = None
    protein: Optional[float] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius: Optional[float] = None

class CypherGenerator:
    """Generate Cypher queries for GraphRAG agent.
    
    This class handles the generation of Cypher queries for different types of data
    based on intent data and conditions.
    
    Attributes:
        _logger: Logger instance for the class
    """
    
    def __init__(self):
        """Initialize CypherGenerator with required components."""
        self._logger = logging.getLogger('agent.graphrag.cypher')
        
    def generate_query(self, intent_data: Dict[str, Any]) -> str:
        """Generate Cypher query based on intent data.
        
        Args:
            intent_data: Dictionary containing intent information
            
        Returns:
            str containing the generated Cypher query
            
        Raises:
            ValueError: If intent_data is invalid or query type is not supported
        """
        if not intent_data:
            raise ValueError("intent_data cannot be empty")
            
        try:
            log_info("Generating Cypher query from intent data")
            
            # Get query type
            query_type = self._get_query_type(intent_data)
            if not query_type:
                raise ValueError("Query type not found in intent data")
                
            # Generate query
            query = self._generate_query_by_type(query_type, intent_data)
            
            log_info(f"Successfully generated {query_type} query")
            return query
            
        except Exception as e:
            log_error(f"Error generating query: {str(e)}")
            raise
            
    def _get_query_type(self, intent_data: Dict[str, Any]) -> Optional[str]:
        """Get query type from intent data.
        
        Args:
            intent_data: Dictionary containing intent information
            
        Returns:
            Optional[str] containing the query type
        """
        return intent_data.get("query_type")
        
    def _generate_query_by_type(self, query_type: str, intent_data: Dict[str, Any]) -> str:
        """Generate query based on type.
        
        Args:
            query_type: Type of query to generate
            intent_data: Dictionary containing intent information
            
        Returns:
            str containing the generated query
            
        Raises:
            ValueError: If query type is not supported
        """
        query_generators = {
            "product": self._generate_product_query,
            "category": self._generate_category_query,
            "store": self._generate_store_query
        }
        
        generator = query_generators.get(query_type)
        if not generator:
            raise ValueError(f"Unsupported query type: {query_type}")
            
        return generator(intent_data)
            
    def _generate_product_query(self, intent_data: Dict[str, Any]) -> str:
        """Generate product query.
        
        Args:
            intent_data: Dictionary containing intent information
            
        Returns:
            str containing the generated product query
        """
        conditions = self._get_product_conditions(intent_data)
        
        return f"""
        MATCH (p:Product)-[:BELONGS_TO_CATEGORY]->(c:Category)
        MATCH (v:Variant)-[:PRODUCT_ID]->(p)
        WHERE {" AND ".join(conditions)}
        RETURN p.id as product_id, p.name as product_name, p.descriptions as product_description,
               c.id as category_id, c.name_cat as category_name, c.description as category_description,
               v.id as variant_id, v.name as variant_name, v.price as variant_price, v.sugar as variant_sugar,
               v.caffeine as variant_caffeine, v.calories as variant_calories, v.protein as variant_protein,
               v.image_url as variant_image_url, v.is_available as variant_is_available, v.is_new as variant_is_new,
               v.is_promotion as variant_is_promotion, v.promotion_price as variant_promotion_price,
               v.promotion_start_date as variant_promotion_start_date, v.promotion_end_date as variant_promotion_end_date,
               v.promotion_description as variant_promotion_description, v.promotion_image_url as variant_promotion_image_url
        ORDER BY v.sales_rank ASC
        LIMIT 10
        """

def generate_cypher_query(intent_data: Dict[str, Any]) -> str:
    """Generate Cypher query based on intent data.
    
    This is a convenience function that wraps the CypherGenerator class.
    
    Args:
        intent_data: Dictionary containing intent information
        
    Returns:
        str containing the generated Cypher query
        
    Raises:
        ValueError: If intent_data is invalid or query type is not supported
    """
    generator = CypherGenerator()
    return generator.generate_query(intent_data)
