"""
LangGraph builder for agent workflow
"""
from typing import Dict, Any, List, Literal, TypedDict, Optional, Union, Annotated
from enum import Enum
import operator
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from ..agents.customer_agent.logic import CustomerAgent
from ..agents.preference_agent.logic import PreferenceAgent
from ..agents.chathistory_agent.logic import ChatHistoryAgent
from ..agents.graphrag_agent.logic import GraphRAGAgent
from ..agents.image_agent.logic import ImageAgent
from ..agents.recommend_agent.logic import RecommendAgent
from ..utils.logger import log_info, log_error

# Define state types
class AgentState(TypedDict):
    """State for the agent workflow"""
    messages: List[Union[HumanMessage, AIMessage]]
    customer_info: Optional[Dict[str, Any]]
    chat_history: Optional[List[Dict[str, Any]]]
    preferences: Optional[Dict[str, Any]]
    image_path: Optional[str]
    query_results: Optional[List[Dict[str, Any]]]  # Results from GraphRAG agent
    recommendations: Optional[List[Dict[str, Any]]]
    next: Optional[str]

class AgentType(str, Enum):
    """Types of agents in the workflow"""
    CUSTOMER = "customer"
    PREFERENCE = "preference"
    CHATHISTORY = "chathistory"
    GRAPHRAG = "graphrag"
    IMAGE = "image"
    RECOMMEND = "recommend"
    ROUTER = "router"

# Initialize agents
customer_agent = CustomerAgent()
preference_agent = PreferenceAgent()
chathistory_agent = ChatHistoryAgent()
graphrag_agent = GraphRAGAgent()
image_agent = ImageAgent()
recommend_agent = RecommendAgent()

def build_workflow() -> StateGraph:
    """Build the LangGraph workflow"""
    # Define the workflow graph
    workflow = StateGraph(AgentState)

    # Add nodes for each agent
    workflow.add_node(AgentType.CUSTOMER, customer_node)
    workflow.add_node(AgentType.PREFERENCE, preference_node)
    workflow.add_node(AgentType.CHATHISTORY, chathistory_node)
    workflow.add_node(AgentType.GRAPHRAG, graphrag_node)
    workflow.add_node(AgentType.IMAGE, image_node)
    workflow.add_node(AgentType.RECOMMEND, recommend_node)
    workflow.add_node(AgentType.ROUTER, router_node)

    # Define the edges
    workflow.add_edge(AgentType.ROUTER, AgentType.CUSTOMER, should_route_to_customer)
    workflow.add_edge(AgentType.ROUTER, AgentType.IMAGE, should_route_to_image)
    workflow.add_edge(AgentType.ROUTER, AgentType.GRAPHRAG, should_route_to_graphrag)
    workflow.add_edge(AgentType.ROUTER, AgentType.PREFERENCE, should_route_to_preference)
    workflow.add_edge(AgentType.ROUTER, AgentType.CHATHISTORY, should_route_to_chathistory)

    # All agents can route to recommend agent
    workflow.add_edge(AgentType.CUSTOMER, AgentType.RECOMMEND)
    workflow.add_edge(AgentType.PREFERENCE, AgentType.RECOMMEND)
    workflow.add_edge(AgentType.CHATHISTORY, AgentType.RECOMMEND)
    workflow.add_edge(AgentType.GRAPHRAG, AgentType.RECOMMEND)
    workflow.add_edge(AgentType.IMAGE, AgentType.RECOMMEND)

    # Recommend agent is the final step
    workflow.add_edge(AgentType.RECOMMEND, END)

    # Set the entry point
    workflow.set_entry_point(AgentType.ROUTER)

    return workflow

# Node functions
def router_node(state: AgentState) -> AgentState:
    """Router node to determine which agent to use"""
    # This is just a passthrough node, the routing is done in the edge conditions
    return state

def customer_node(state: AgentState) -> AgentState:
    """Customer agent node"""
    try:
        # Get the last message
        last_message = state["messages"][-1]

        if isinstance(last_message, HumanMessage):
            # Process the message with customer agent
            response = customer_agent.process_message(last_message.content)

            # Update customer info in state
            if state.get("customer_info") is None:
                # Try to get customer info from session
                from flask import session
                user_id = session.get('user_id')
                if user_id:
                    customer_info = customer_agent.get_customer_info(user_id)
                    if customer_info:
                        state["customer_info"] = customer_info

            # Add response to messages
            state["messages"].append(AIMessage(content=response))

        return state
    except Exception as e:
        log_error(f"Error in customer node: {str(e)}")
        state["messages"].append(AIMessage(content="Xin lỗi, đã xảy ra lỗi khi xử lý thông tin khách hàng."))
        return state

def preference_node(state: AgentState) -> AgentState:
    """Preference agent node"""
    try:
        # Get the last message
        last_message = state["messages"][-1]

        if isinstance(last_message, HumanMessage):
            # Create context
            context = {
                "customer": state.get("customer_info"),
                "chat_history": state.get("chat_history")
            }

            # Process the message with preference agent
            response = preference_agent.process_message(last_message.content, context)

            # Update preferences in state
            if state.get("customer_info"):
                preferences = preference_agent.analyze_preferences(
                    state["customer_info"],
                    state.get("chat_history")
                )
                state["preferences"] = preferences

            # Add response to messages
            state["messages"].append(AIMessage(content=response))

        return state
    except Exception as e:
        log_error(f"Error in preference node: {str(e)}")
        state["messages"].append(AIMessage(content="Xin lỗi, đã xảy ra lỗi khi phân tích sở thích."))
        return state

def chathistory_node(state: AgentState) -> AgentState:
    """Chat history agent node"""
    try:
        # Get the last message
        last_message = state["messages"][-1]

        if isinstance(last_message, HumanMessage):
            # Create context
            context = {
                "chat_history": state.get("chat_history")
            }

            # Process the message with chathistory agent
            response = chathistory_agent.process_message(last_message.content, context)

            # Add response to messages
            state["messages"].append(AIMessage(content=response))

        return state
    except Exception as e:
        log_error(f"Error in chathistory node: {str(e)}")
        state["messages"].append(AIMessage(content="Xin lỗi, đã xảy ra lỗi khi phân tích lịch sử chat."))
        return state

def graphrag_node(state: AgentState) -> AgentState:
    """GraphRAG agent node"""
    try:
        # Get the last message
        last_message = state["messages"][-1]

        if isinstance(last_message, HumanMessage):
            # Create context
            context = {
                "customer": state.get("customer_info"),
                "chat_history": state.get("chat_history")
            }

            # Process the message with graphrag agent
            # GraphRAG agent now only generates and executes Cypher queries
            query_results = graphrag_agent.execute_query(last_message.content, context)

            # Store query results in state for recommend agent
            state["query_results"] = query_results

            # Set next agent to recommend
            state["next"] = AgentType.RECOMMEND

        return state
    except Exception as e:
        log_error(f"Error in graphrag node: {str(e)}")
        state["messages"].append(AIMessage(content="Xin lỗi, đã xảy ra lỗi khi truy vấn cơ sở dữ liệu."))
        return state

def image_node(state: AgentState) -> AgentState:
    """Image agent node"""
    try:
        # Get the last message
        last_message = state["messages"][-1]

        if isinstance(last_message, HumanMessage) and state.get("image_path"):
            # Process the message with image agent
            response = image_agent.process_message(last_message.content, state["image_path"])

            # Add response to messages
            state["messages"].append(AIMessage(content=response))

        return state
    except Exception as e:
        log_error(f"Error in image node: {str(e)}")
        state["messages"].append(AIMessage(content="Xin lỗi, đã xảy ra lỗi khi xử lý hình ảnh."))
        return state

def recommend_node(state: AgentState) -> AgentState:
    """Recommendation agent node"""
    try:
        # Get the last message
        last_message = state["messages"][-1]

        if isinstance(last_message, HumanMessage):
            # Create context
            context = {
                "customer": state.get("customer_info"),
                "chat_history": state.get("chat_history"),
                "preferences": state.get("preferences"),
                "query_results": state.get("query_results")  # Add query results from GraphRAG agent
            }

            # Process the message with recommend agent
            response = recommend_agent.process_message(last_message.content, context)

            # Add response to messages
            state["messages"].append(AIMessage(content=response))

        return state
    except Exception as e:
        log_error(f"Error in recommend node: {str(e)}")
        state["messages"].append(AIMessage(content="Xin lỗi, đã xảy ra lỗi khi đưa ra gợi ý."))
        return state

# Edge conditions
def should_route_to_customer(state: AgentState) -> bool:
    """Check if should route to customer agent"""
    if state.get("next") == AgentType.CUSTOMER:
        return True

    # Check if message contains customer-related keywords
    last_message = state["messages"][-1]
    if isinstance(last_message, HumanMessage):
        content = last_message.content.lower()
        customer_keywords = ["thông tin", "tài khoản", "hồ sơ", "đơn hàng", "lịch sử"]
        return any(keyword in content for keyword in customer_keywords)

    return False

def should_route_to_image(state: AgentState) -> bool:
    """Check if should route to image agent"""
    # If there's an image path, route to image agent
    return state.get("image_path") is not None

def should_route_to_graphrag(state: AgentState) -> bool:
    """Check if should route to graphrag agent"""
    if state.get("next") == AgentType.GRAPHRAG:
        return True

    # Default route if no other condition matches
    return not any([
        should_route_to_customer(state),
        should_route_to_image(state),
        should_route_to_preference(state),
        should_route_to_chathistory(state)
    ])

def should_route_to_preference(state: AgentState) -> bool:
    """Check if should route to preference agent"""
    if state.get("next") == AgentType.PREFERENCE:
        return True

    # Check if message contains preference-related keywords
    last_message = state["messages"][-1]
    if isinstance(last_message, HumanMessage):
        content = last_message.content.lower()
        preference_keywords = ["thích", "sở thích", "ưa thích", "yêu thích", "gợi ý", "đề xuất"]
        return any(keyword in content for keyword in preference_keywords)

    return False

def should_route_to_chathistory(state: AgentState) -> bool:
    """Check if should route to chathistory agent"""
    if state.get("next") == AgentType.CHATHISTORY:
        return True

    # Check if message contains chathistory-related keywords
    last_message = state["messages"][-1]
    if isinstance(last_message, HumanMessage):
        content = last_message.content.lower()
        chathistory_keywords = ["lịch sử chat", "trò chuyện", "nói chuyện", "đã nói"]
        return any(keyword in content for keyword in chathistory_keywords)

    return False
