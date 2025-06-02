"""
Variant processor for GraphRAG agent.

This module provides functionality to process and extract information from variant communities,
including:
- Variant filtering and sorting
- Product information extraction
- Variant details retrieval
- Top variants selection
"""
from typing import Dict, List, Any, Optional, Set, Tuple
import json
import logging
from dataclasses import dataclass
from datetime import datetime

from app.utils.logger import log_info, log_error
from app.neo4j_client.connection import execute_query
from ..core.constants import QUERY_TEMPLATES

@dataclass
class VariantInfo:
    """Data class for storing variant information"""
    id: str
    name: str
    description: str
    category: Dict[str, str]
    beverage_option: str
    price: float
    sugar: float
    caffeine: float
    calories: float
    protein: float
    sales_rank: int

@dataclass
class ProductInfo:
    """Data class for storing product information"""
    product_id: str
    product_name: str
    product_description: str
    category_id: str
    category_name: str

@dataclass
class VariantCommunity:
    """Data class for storing variant community information"""
    id: str
    product_community_id: Optional[str] = None
    product_info: Optional[Dict[str, Any]] = None

class VariantProcessor:
    """Process variants for GraphRAG agent.
    
    This class handles the processing of variants based on intent data, including:
    - Filtering variants based on constraints
    - Sorting variants based on criteria
    - Formatting variants for response
    
    Attributes:
        _logger: Logger instance for the class
    """
    
    def __init__(self):
        """Initialize VariantProcessor with required components."""
        self._logger = logging.getLogger('agent.graphrag.variant')
        
    def process_variants(self, variants: List[Dict[str, Any]], intent_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process variants based on intent data.
        
        Args:
            variants: List of variant dictionaries to process
            intent_data: Dictionary containing intent information
            
        Returns:
            List of processed variant dictionaries
            
        Raises:
            ValueError: If variants is None
        """
        if variants is None:
            raise ValueError("variants cannot be None")
            
        try:
            log_info(f"Processing {len(variants)} variants")
            
            # Filter variants
            filtered_variants = self._filter_variants(variants, intent_data)
            
            # Sort variants
            sorted_variants = self._sort_variants(filtered_variants, intent_data)
            
            # Format variants
            formatted_variants = self._format_variants(sorted_variants)
            
            log_info(f"Successfully processed {len(formatted_variants)} variants")
            return formatted_variants
            
        except Exception as e:
            log_error(f"Error processing variants: {str(e)}")
            raise
            
    def _filter_variants(self, variants: List[Dict[str, Any]], intent_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Filter variants based on intent data.
        
        Args:
            variants: List of variant dictionaries to filter
            intent_data: Dictionary containing intent information
            
        Returns:
            List of filtered variant dictionaries
        """
        return [variant for variant in variants if self._matches_intent(variant, intent_data)]
        
    def _matches_intent(self, variant: Dict[str, Any], intent_data: Dict[str, Any]) -> bool:
        """Check if variant matches intent data.
        
        Args:
            variant: Dictionary containing variant information
            intent_data: Dictionary containing intent information
            
        Returns:
            bool indicating if variant matches intent data
        """
        constraints = {
            "price": variant.get("price", float("inf")),
            "sugar": variant.get("sugar", float("inf")),
            "caffeine": variant.get("caffeine", float("inf")),
            "calories": variant.get("calories", float("inf")),
            "protein": variant.get("protein", float("inf"))
        }
        
        for key, value in constraints.items():
            if key in intent_data and value > intent_data[key]:
                return False
                
        return True
        
    def _sort_variants(self, variants: List[Dict[str, Any]], intent_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Sort variants based on intent data.
        
        Args:
            variants: List of variant dictionaries to sort
            intent_data: Dictionary containing intent information
            
        Returns:
            List of sorted variant dictionaries
        """
        sort_key = self._get_sort_key(intent_data)
        reverse = intent_data.get("sort_order") == "desc"
        
        return sorted(variants, key=lambda x: x.get(sort_key, 0), reverse=reverse)
        
    def _get_sort_key(self, intent_data: Dict[str, Any]) -> str:
        """Get sort key from intent data.
        
        Args:
            intent_data: Dictionary containing intent information
            
        Returns:
            str containing the sort key
        """
        return intent_data.get("sort_by", "sales_rank")
        
    def _format_variants(self, variants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format variants for response.
        
        Args:
            variants: List of variant dictionaries to format
            
        Returns:
            List of formatted variant dictionaries
        """
        return [VariantInfo(
            id=variant["variant_id"],
            name=variant["product_name"],
            description=variant["product_description"],
            category={
                "id": variant["category_id"],
                "name": variant["category_name"],
                "description": variant["category_description"]
            },
            beverage_option=variant["beverage_option"],
            price=variant["price"],
            sugar=variant["sugar"],
            caffeine=variant["caffeine"],
            calories=variant["calories"],
            protein=variant["protein"],
            sales_rank=variant["sales_rank"]
        ).__dict__ for variant in variants]

def extract_product_info_from_variant_communities(variant_communities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract product information from variant communities.
    
    Args:
        variant_communities: List of variant community dictionaries
        
    Returns:
        List of enriched variant community dictionaries
        
    Raises:
        ValueError: If variant_communities is None
    """
    if variant_communities is None:
        raise ValueError("variant_communities cannot be None")
        
    if not variant_communities:
        log_info("No variant communities to extract product information from")
        return []

    # Get unique product community IDs
    product_community_ids = {
        community["product_community_id"]
        for community in variant_communities
        if "product_community_id" in community
    }

    log_info(f"Found {len(product_community_ids)} unique product communities from variant communities")

    # Get detailed product information from Neo4j
    product_info = get_product_info_from_communities(product_community_ids)

    # Combine product information with variant information
    return [
        {
            **community,
            "product_info": product_info.get(community.get("product_community_id"), {})
        }
        for community in variant_communities
    ]

def get_product_info_from_communities(product_community_ids: Set[Any]) -> Dict[Any, Dict[str, Any]]:
    """Get detailed product information from product communities.
    
    Args:
        product_community_ids: Set of product community IDs
        
    Returns:
        Dictionary mapping product community IDs to product information
        
    Raises:
        ValueError: If product_community_ids is None
    """
    if product_community_ids is None:
        raise ValueError("product_community_ids cannot be None")
        
    if not product_community_ids:
        return {}

    query = """
    MATCH (pc:ProductCommunity)-[:CONTAINS_PRODUCT]->(p:Product)-[:BELONGS_TO_CATEGORY]->(c:Category)
    WHERE pc.id IN $product_community_ids
    RETURN pc.id AS product_community_id,
           COALESCE(p.id, ID(p)) AS product_id,
           p.name AS product_name,
           p.descriptions AS product_description,
           COALESCE(c.id, ID(c)) AS category_id,
           c.name_cat AS category_name
    """

    try:
        result = execute_query(query, {"product_community_ids": list(product_community_ids)})
        product_info = {}

        for record in result:
            product_community_id = record["product_community_id"]
            if product_community_id not in product_info:
                product_info[product_community_id] = {"products": []}

            product_info[product_community_id]["products"].append(ProductInfo(
                product_id=record["product_id"],
                product_name=record["product_name"],
                product_description=record["product_description"],
                category_id=record["category_id"],
                category_name=record["category_name"]
            ).__dict__)

        log_info(f"Retrieved information for {len(product_info)} product communities")
        return product_info

    except Exception as e:
        log_error(f"Error retrieving product information from communities: {str(e)}")
        raise

def get_variant_details(variant_communities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Get detailed variant information from Neo4j.
    
    Args:
        variant_communities: List of variant community dictionaries
        
    Returns:
        List of enriched variant community dictionaries
        
    Raises:
        ValueError: If variant_communities is None
    """
    if variant_communities is None:
        raise ValueError("variant_communities cannot be None")
        
    if not variant_communities:
        return []

    # Get variant community IDs
    variant_community_ids = [
        community["id"]
        for community in variant_communities
        if "id" in community
    ]

    query = """
    MATCH (vc:VariantCommunity)-[:CONTAINS_VARIANT]->(v:Variant)-[:PRODUCT_ID]->(p:Product)-[:BELONGS_TO_CATEGORY]->(c:Category)
    WHERE vc.id IN $variant_community_ids
    RETURN vc.id AS variant_community_id,
           v.id AS variant_id,
           v.name AS variant_name,
           v.description AS variant_description,
           p.id AS product_id,
           p.name AS product_name,
           p.description AS product_description,
           c.id AS category_id,
           c.name AS category_name,
           c.description AS category_description
    """

    try:
        result = execute_query(query, {"variant_community_ids": variant_community_ids})
        variant_details = {}

        for record in result:
            variant_community_id = record["variant_community_id"]
            if variant_community_id not in variant_details:
                variant_details[variant_community_id] = {
                    "variants": [],
                    "product_info": {
                        "product_id": record["product_id"],
                        "product_name": record["product_name"],
                        "product_description": record["product_description"],
                        "category_id": record["category_id"],
                        "category_name": record["category_name"],
                        "category_description": record["category_description"]
                    }
                }

            variant_details[variant_community_id]["variants"].append({
                "variant_id": record["variant_id"],
                "variant_name": record["variant_name"],
                "variant_description": record["variant_description"]
            })

        log_info(f"Retrieved details for {len(variant_details)} variant communities")
        return list(variant_details.values())

    except Exception as e:
        log_error(f"Error retrieving variant details: {str(e)}")
        raise

def get_top_variants_from_communities(variant_communities: List[Dict[str, Any]], max_variants_per_community: int = 3) -> List[Dict[str, Any]]:
    """Get top variants from communities.
    
    Args:
        variant_communities: List of variant community dictionaries
        max_variants_per_community: Maximum number of variants to return per community
        
    Returns:
        List of top variant dictionaries
        
    Raises:
        ValueError: If variant_communities is None or max_variants_per_community is invalid
    """
    if variant_communities is None:
        raise ValueError("variant_communities cannot be None")
        
    if max_variants_per_community < 1:
        raise ValueError("max_variants_per_community must be greater than 0")

    top_variants = []
    for community in variant_communities:
        variants = community.get("variants", [])
        sorted_variants = sorted(variants, key=lambda x: x.get("sales_rank", float("inf")))
        top_variants.extend(sorted_variants[:max_variants_per_community])

    log_info(f"Retrieved {len(top_variants)} top variants from {len(variant_communities)} communities")
    return top_variants

def extract_variant_info_for_response(variant_communities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract variant information for response.
    
    Args:
        variant_communities: List of variant community dictionaries
        
    Returns:
        Dictionary containing extracted variant information
        
    Raises:
        ValueError: If variant_communities is None
    """
    if variant_communities is None:
        raise ValueError("variant_communities cannot be None")

    response_data = {
        "total_communities": len(variant_communities),
        "total_variants": sum(len(community.get("variants", [])) for community in variant_communities),
        "communities": []
    }

    for community in variant_communities:
        community_info = {
            "id": community.get("id"),
            "product_info": community.get("product_info", {}),
            "variants": community.get("variants", [])
        }
        response_data["communities"].append(community_info)

    log_info(f"Extracted information for {response_data['total_communities']} communities with {response_data['total_variants']} variants")
    return response_data
