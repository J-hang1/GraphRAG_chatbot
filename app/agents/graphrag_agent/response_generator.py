"""
Response generator for GraphRAG agent.

This module provides functionality to generate natural language responses from query results,
including:
- Empty result responses
- Store information responses
- Order information responses
- Product information responses
"""
from typing import Dict, Any, List, Optional, Union
import json
import logging
from dataclasses import dataclass
from ...utils.logger import log_info, log_error

@dataclass
class StoreInfo:
    """Data class for storing store information"""
    name: str
    address: str
    phone: Optional[str] = None
    open_close: Optional[str] = None

@dataclass
class OrderInfo:
    """Data class for storing order information"""
    id: str
    order_date: str
    name_product: str
    beverage_option: str
    quantity: int
    price: float
    name_store: str

@dataclass
class ProductInfo:
    """Data class for storing product information"""
    name: str
    category: str
    beverage_option: str
    price: float
    calories: Optional[float] = None
    caffeine_mg: Optional[float] = None
    protein_g: Optional[float] = None
    sugars_g: Optional[float] = None

class ResponseGenerator:
    """Response generator for GraphRAG agent.
    
    This class handles the generation of natural language responses from query results,
    including:
    - Empty result responses
    - Store information responses
    - Order information responses
    - Product information responses
    
    Attributes:
        _logger: Logger instance for the class
    """
    
    def __init__(self):
        """Initialize ResponseGenerator with required components."""
        self._logger = logging.getLogger('agent.graphrag.response')
        
    def generate_response(self, query_result: List[Dict[str, Any]], intent_data: Dict[str, Any]) -> str:
        """Generate response from query result and intent data.
        
        Args:
            query_result: List of dictionaries containing query results
            intent_data: Dictionary containing intent information
            
        Returns:
            str containing the generated response
            
        Raises:
            ValueError: If query_result is None
        """
        if query_result is None:
            raise ValueError("query_result cannot be None")
            
        try:
            log_info("Generating response from query result")
            
            # Check if query result is empty
            if not query_result:
                return self._generate_empty_response(intent_data)
                
            # Generate response based on query type
            query_type = intent_data.get("query_type", "product")
            response_generators = {
                "store": self._generate_store_response,
                "order": self._generate_order_response,
                "product": self._generate_product_response
            }
            
            generator = response_generators.get(query_type, self._generate_product_response)
            return generator(query_result, intent_data)
                
        except Exception as e:
            log_error(f"Error generating response: {str(e)}")
            raise
            
    def _generate_empty_response(self, intent_data: Dict[str, Any]) -> str:
        """Generate response when query result is empty.
        
        Args:
            intent_data: Dictionary containing intent information
            
        Returns:
            str containing the empty response
        """
        query_type = intent_data.get("query_type", "product")
        empty_responses = {
            "store": "Sorry, I couldn't find any store information matching your request.",
            "order": "Sorry, I couldn't find any order information matching your request.",
            "product": "Sorry, I couldn't find any products matching your request."
        }
        return empty_responses.get(query_type, empty_responses["product"])
            
    def _generate_store_response(self, query_result: List[Dict[str, Any]], intent_data: Dict[str, Any]) -> str:
        """Generate response for store query.
        
        Args:
            query_result: List of dictionaries containing store information
            intent_data: Dictionary containing intent information
            
        Returns:
            str containing the store response
        """
        try:
            # Format store information
            store_info = []
            for store in query_result:
                info = StoreInfo(
                    name=store['name_store'],
                    address=store['address'],
                    phone=store.get('phone'),
                    open_close=store.get('open_close')
                )
                
                store_text = f"- {info.name}: {info.address}"
                if info.phone:
                    store_text += f" (Phone: {info.phone})"
                if info.open_close:
                    store_text += f" - Opening hours: {info.open_close}"
                store_info.append(store_text)
                
            # Generate response
            response = "Here is the store information:\n"
            response += "\n".join(store_info)
            
            return response
            
        except Exception as e:
            log_error(f"Error generating store response: {str(e)}")
            raise
            
    def _generate_order_response(self, query_result: List[Dict[str, Any]], intent_data: Dict[str, Any]) -> str:
        """Generate response for order query.
        
        Args:
            query_result: List of dictionaries containing order information
            intent_data: Dictionary containing intent information
            
        Returns:
            str containing the order response
        """
        try:
            # Format order information
            order_info = []
            for order in query_result:
                info = OrderInfo(
                    id=order['id'],
                    order_date=order['order_date'],
                    name_product=order['name_product'],
                    beverage_option=order['Beverage_Option'],
                    quantity=order['quantity'],
                    price=order['price'],
                    name_store=order['name_store']
                )
                
                order_text = f"- Order #{info.id} ({info.order_date}):\n"
                order_text += f"  + Product: {info.name_product} ({info.beverage_option})\n"
                order_text += f"  + Quantity: {info.quantity}\n"
                order_text += f"  + Price: {info.price} VND\n"
                order_text += f"  + Store: {info.name_store}"
                order_info.append(order_text)
                
            # Generate response
            response = "Here is your order information:\n"
            response += "\n".join(order_info)
            
            return response
            
        except Exception as e:
            log_error(f"Error generating order response: {str(e)}")
            raise
            
    def _generate_product_response(self, query_result: List[Dict[str, Any]], intent_data: Dict[str, Any]) -> str:
        """Generate response for product query.
        
        Args:
            query_result: List of dictionaries containing product information
            intent_data: Dictionary containing intent information
            
        Returns:
            str containing the product response
        """
        try:
            # Format product information
            product_info = []
            for product in query_result:
                info = ProductInfo(
                    name=product['name_product'],
                    category=product['name_cat'],
                    beverage_option=product['Beverage_Option'],
                    price=product['price'],
                    calories=product.get('calories'),
                    caffeine_mg=product.get('caffeine_mg'),
                    protein_g=product.get('protein_g'),
                    sugars_g=product.get('sugars_g')
                )
                
                product_text = f"- {info.name} ({info.category}):\n"
                product_text += f"  + Option: {info.beverage_option}\n"
                product_text += f"  + Price: {info.price} VND"
                
                # Add nutritional information if available
                if info.calories:
                    product_text += f"\n  + Calories: {info.calories} kcal"
                if info.caffeine_mg:
                    product_text += f"\n  + Caffeine: {info.caffeine_mg} mg"
                if info.protein_g:
                    product_text += f"\n  + Protein: {info.protein_g} g"
                if info.sugars_g:
                    product_text += f"\n  + Sugar: {info.sugars_g} g"
                    
                product_info.append(product_text)
                
            # Generate response
            response = "Here is the product information:\n"
            response += "\n".join(product_info)
            
            return response
            
        except Exception as e:
            log_error(f"Error generating product response: {str(e)}")
            raise 