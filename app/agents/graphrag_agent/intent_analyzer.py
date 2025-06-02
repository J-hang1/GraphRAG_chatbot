"""
Intent analyzer for GraphRAG agent.

This module provides functionality to analyze user intents from messages, including:
- Query type analysis
- Intent classification
- Keyword extraction
- Entity extraction
- Constraint extraction
- Sort information extraction
"""
from typing import Dict, Any, List, Optional, Union, Set, Pattern
import json
import logging
import re
from dataclasses import dataclass
from ...utils.logger import log_info, log_error
from ..core.constants import QUERY_KEYWORDS, STATISTICAL_PATTERNS

@dataclass
class IntentData:
    """Data class for storing intent information"""
    query_type: Optional[str] = None
    intent: Optional[str] = None
    keywords: List[str] = None
    entities: List[str] = None
    constraints: Dict[str, Any] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None
    chat_history: Optional[List[Dict[str, Any]]] = None
    preferences: Optional[Dict[str, Any]] = None
    mentioned_entities: Optional[List[str]] = None

    def __post_init__(self):
        """Initialize default values for mutable fields"""
        if self.keywords is None:
            self.keywords = []
        if self.entities is None:
            self.entities = []
        if self.constraints is None:
            self.constraints = {}

@dataclass
class SortInfo:
    """Data class for storing sort information"""
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None

class IntentAnalyzer:
    """Intent analyzer for GraphRAG agent.
    
    This class handles the analysis of user intents from messages, including:
    - Query type analysis
    - Intent classification
    - Keyword extraction
    - Entity extraction
    - Constraint extraction
    - Sort information extraction
    
    Attributes:
        _logger: Logger instance for the class
    """
    
    def __init__(self):
        """Initialize IntentAnalyzer with required components."""
        self._logger = logging.getLogger('agent.graphrag.intent')
        
    def analyze_intent(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze intent from message.
        
        Args:
            message: The message to analyze
            context: Optional context information
            
        Returns:
            Dict containing analyzed intent data
            
        Raises:
            ValueError: If message is empty
        """
        if not message:
            raise ValueError("message cannot be empty")
            
        try:
            log_info("Analyzing intent from message")
            
            # Initialize intent data
            intent_data = IntentData()
            
            # Analyze query type
            intent_data.query_type = self._analyze_query_type(message)
            
            # Analyze intent
            intent_data.intent = self._analyze_intent(message)
            
            # Extract keywords
            intent_data.keywords = self._extract_keywords(message)
            
            # Extract entities
            intent_data.entities = self._extract_entities(message)
            
            # Extract constraints
            intent_data.constraints = self._extract_constraints(message)
            
            # Extract sort information
            sort_info = self._extract_sort_info(message)
            intent_data.sort_by = sort_info.sort_by
            intent_data.sort_order = sort_info.sort_order
            
            # Add context if available
            if context:
                intent_data = self._add_context_to_intent(intent_data, context)
                
            log_info(f"Successfully analyzed intent: {json.dumps(intent_data.__dict__, ensure_ascii=False)}")
            return intent_data.__dict__
            
        except Exception as e:
            log_error(f"Error analyzing intent: {str(e)}")
            raise
            
    def _analyze_query_type(self, message: str) -> str:
        """Analyze query type from message.
        
        Args:
            message: The message to analyze
            
        Returns:
            str containing the query type
        """
        message_lower = message.lower()
        
        # Check for store keywords
        if any(keyword in message_lower for keyword in QUERY_KEYWORDS["store"]):
            return "store"
            
        # Check for order keywords
        if any(keyword in message_lower for keyword in QUERY_KEYWORDS["order"]):
            return "order"
            
        # Default to product query
        return "product"
        
    def _analyze_intent(self, message: str) -> str:
        """Analyze main intent from message.
        
        Args:
            message: The message to analyze
            
        Returns:
            str containing the main intent
        """
        message_lower = message.lower()
        
        # Check for statistical patterns
        for pattern in STATISTICAL_PATTERNS:
            if pattern["pattern"].search(message_lower):
                return pattern["type"]
                
        # Default intent
        return "search"
        
    def _extract_keywords(self, message: str) -> List[str]:
        """Extract keywords from message.
        
        Args:
            message: The message to analyze
            
        Returns:
            List[str] containing extracted keywords
        """
        keywords = []
        message_lower = message.lower()
        
        # Extract keywords based on patterns
        for pattern in STATISTICAL_PATTERNS:
            match = pattern["pattern"].search(message_lower)
            if match:
                keywords.append(match.group(1))
                
        return list(set(keywords))  # Remove duplicates
        
    def _extract_entities(self, message: str) -> List[str]:
        """Extract entities from message.
        
        Args:
            message: The message to analyze
            
        Returns:
            List[str] containing extracted entities
        """
        entities = []
        message_lower = message.lower()
        
        # Extract entities based on patterns
        for pattern in STATISTICAL_PATTERNS:
            match = pattern["pattern"].search(message_lower)
            if match:
                entities.append(match.group(2))
                
        return list(set(entities))  # Remove duplicates
        
    def _extract_constraints(self, message: str) -> Dict[str, Any]:
        """Extract constraints from message.
        
        Args:
            message: The message to analyze
            
        Returns:
            Dict containing extracted constraints
        """
        constraints = {}
        message_lower = message.lower()
        
        # Extract constraints based on patterns
        for pattern in STATISTICAL_PATTERNS:
            match = pattern["pattern"].search(message_lower)
            if match:
                constraints[pattern["attribute"]] = {
                    "value": float(match.group(1)),
                    "condition": pattern["condition"]
                }
                
        return constraints
        
    def _extract_sort_info(self, message: str) -> SortInfo:
        """Extract sort information from message.
        
        Args:
            message: The message to analyze
            
        Returns:
            SortInfo containing sort information
        """
        sort_info = SortInfo()
        message_lower = message.lower()
        
        # Extract sort information based on patterns
        for pattern in STATISTICAL_PATTERNS:
            match = pattern["pattern"].search(message_lower)
            if match:
                sort_info.sort_by = pattern["attribute"]
                sort_info.sort_order = pattern["condition"]
                break
                
        return sort_info
        
    def _add_context_to_intent(self, intent_data: IntentData, context: Dict[str, Any]) -> IntentData:
        """Add context to intent data.
        
        Args:
            intent_data: The intent data to enrich
            context: Dictionary containing context information
            
        Returns:
            IntentData enriched with context information
        """
        # Add chat history
        if "chat_history" in context:
            intent_data.chat_history = context["chat_history"]
            
        # Add user preferences
        if "preferences" in context:
            intent_data.preferences = context["preferences"]
            
        # Add mentioned entities
        if "mentioned_entities" in context:
            intent_data.mentioned_entities = context["mentioned_entities"]
            
        return intent_data 