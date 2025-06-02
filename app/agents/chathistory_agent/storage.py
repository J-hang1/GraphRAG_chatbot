"""
Module for storing chat history
"""
from typing import Dict, Any, List, Protocol, Optional
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from collections import deque
from ...utils.logger import log_info, log_error

class ChatHistoryStorage(ABC):
    """Abstract class for chat history storage"""

    @abstractmethod
    def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Get session data for session_id, create new if not exists

        Args:
            session_id (str): Session ID

        Returns:
            Dict[str, Any]: Session data
        """
        pass

    @abstractmethod
    def reset_session(self, session_id: str) -> None:
        """
        Reset session

        Args:
            session_id (str): Session ID
        """
        pass

    @abstractmethod
    def add_message(self, session_id: str, user_message: str, bot_response: str = None, query_details: dict = None) -> None:
        """
        Add message to session

        Args:
            session_id (str): Session ID
            user_message (str): User message
            bot_response (str, optional): Bot response
            query_details (dict, optional): Query details
        """
        pass

    @abstractmethod
    def update_bot_response(self, session_id: str, bot_response: str) -> None:
        """
        Update bot response for the latest message

        Args:
            session_id (str): Session ID
            bot_response (str): Bot response
        """
        pass

    @abstractmethod
    def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get chat history for session_id

        Args:
            session_id (str): Session ID

        Returns:
            List[Dict[str, Any]]: List of messages
        """
        pass

    @abstractmethod
    def set_customer_info(self, session_id: str, customer_id: str, is_authenticated: bool = True) -> None:
        """
        Set customer info for session

        Args:
            session_id (str): Session ID
            customer_id (str): Customer ID
            is_authenticated (bool): Authentication status
        """
        pass

class InMemoryChatHistoryStorage(ChatHistoryStorage):
    """In-memory implementation of chat history storage"""

    def __init__(self, max_history_length: int = 3, session_timeout: int = 30):
        """
        Initialize in-memory chat history storage

        Args:
            max_history_length (int): Maximum number of messages to store in each session
            session_timeout (int): Session timeout in minutes
        """
        self._sessions = {}  # Dict to store session data for each session_id
        self._max_history_length = max_history_length
        self._session_timeout = session_timeout
        log_info(f"Initialized InMemoryChatHistoryStorage with max_history_length={max_history_length}, session_timeout={session_timeout} minutes")

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Get session data for session_id, create new if not exists

        Args:
            session_id (str): Session ID

        Returns:
            Dict[str, Any]: Session data
        """
        # Clean up expired sessions
        self._cleanup_expired_sessions()

        if session_id not in self._sessions:
            # Create new session
            self._sessions[session_id] = {
                'created_at': datetime.now(),
                'last_updated': datetime.now(),
                'history': deque(maxlen=self._max_history_length),  # Limit to recent messages
                'is_authenticated': False,
                'customer_id': None
            }
            log_info(f"Created new chat session for session {session_id}")
        else:
            # Update access time
            self._sessions[session_id]['last_updated'] = datetime.now()

        return self._sessions[session_id]

    def reset_session(self, session_id: str) -> None:
        """
        Reset session

        Args:
            session_id (str): Session ID
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            log_info(f"Reset chat session for session {session_id}")

    def add_message(self, session_id: str, user_message: str, bot_response: str = None, query_details: dict = None) -> None:
        """
        Add message to session

        Args:
            session_id (str): Session ID
            user_message (str): User message
            bot_response (str, optional): Bot response
            query_details (dict, optional): Query details
        """
        try:
            session_data = self.get_session(session_id)

            # Get message number in session
            chat_turn = len(session_data['history']) + 1

            # Create new entry with timestamp
            entry = {
                'chat_turn': chat_turn,
                'user_message': user_message,
                'timestamp': datetime.now().isoformat(),
            }

            # If bot response is provided, add it to entry
            if bot_response:
                entry['bot_response'] = bot_response
                entry['bot_timestamp'] = datetime.now().isoformat()

            # If query details are provided, add them to entry (simplified version)
            if query_details:
                # Add only structured_query and selected_products
                if 'structured_query' in query_details:
                    entry['structured_query'] = query_details['structured_query']
                    log_info(f"Added structured_query to message: {str(query_details['structured_query'])[:100]}...")

                if 'selected_products' in query_details:
                    entry['selected_product_list'] = query_details['selected_products']
                    log_info(f"Added selected_product_list to message: {query_details['selected_products']}")

                # Log what we're not storing anymore
                log_info("Note: cypher_query and cypher_result are no longer stored in chat history")

            # Check if we're about to exceed the max history length
            if len(session_data['history']) >= self._max_history_length:
                log_info(f"History limit reached ({self._max_history_length}). Oldest message will be removed.")
                if len(session_data['history']) > 0:
                    oldest_message = session_data['history'][0]
                    log_info(f"Removing oldest message: {str(oldest_message)[:100]}...")

            # Add to deque (automatically removes old messages if exceeds maxlen)
            session_data['history'].append(entry)
            session_data['last_updated'] = datetime.now()

            # Log the entry that was added
            log_info(f"Added new message to chat session {session_id}: {str(entry)[:200]}...")

            # Log the current state of the history
            log_info(f"Current history for session {session_id} has {len(session_data['history'])} messages")

            # Log the history limit
            log_info(f"History limit is set to {self._max_history_length} messages")

            if bot_response:
                log_info(f"Added bot response to chat session {session_id}")
            if query_details:
                log_info(f"Added query details to chat session {session_id}")
        except Exception as e:
            log_error(f"Error adding message to chat session: {str(e)}")
            import traceback
            log_error(traceback.format_exc())

    def update_bot_response(self, session_id: str, bot_response: str) -> None:
        """
        Update bot response for the latest message

        Args:
            session_id (str): Session ID
            bot_response (str): Bot response
        """
        try:
            session_data = self.get_session(session_id)

            if not session_data['history']:
                log_error("Cannot update bot response: No messages in history")
                return

            # Get latest message
            latest_message = session_data['history'][-1]

            # Update bot response
            latest_message['bot_response'] = bot_response
            latest_message['bot_timestamp'] = datetime.now().isoformat()

            log_info(f"Updated bot response for latest message in session {session_id}")
        except Exception as e:
            log_error(f"Error updating bot response: {str(e)}")

    def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get chat history for session_id

        Args:
            session_id (str): Session ID

        Returns:
            List[Dict[str, Any]]: List of messages
        """
        try:
            session_data = self.get_session(session_id)
            # Convert deque to list for easier use
            history = list(session_data['history'])
            log_info(f"Retrieved {len(history)} messages from session {session_id}")

            # Log the first message to help with debugging
            if history:
                log_info(f"First message in history: {str(history[0])[:200]}...")

                # Log the last message to help with debugging
                if len(history) > 1:
                    log_info(f"Last message in history: {str(history[-1])[:200]}...")

            return history
        except Exception as e:
            log_error(f"Error getting chat history: {str(e)}")
            import traceback
            log_error(traceback.format_exc())
            return []

    def set_customer_info(self, session_id: str, customer_id: str, is_authenticated: bool = True) -> None:
        """
        Set customer info for session

        Args:
            session_id (str): Session ID
            customer_id (str): Customer ID
            is_authenticated (bool): Authentication status
        """
        try:
            session_data = self.get_session(session_id)
            session_data['customer_id'] = customer_id
            session_data['is_authenticated'] = is_authenticated
            session_data['last_updated'] = datetime.now()

            log_info(f"Updated customer info for session {session_id}: customer_id={customer_id}, is_authenticated={is_authenticated}")
        except Exception as e:
            log_error(f"Error updating customer info: {str(e)}")

    def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions"""
        try:
            now = datetime.now()
            expired_sessions = []

            for session_id, session_data in self._sessions.items():
                last_updated = session_data['last_updated']
                if now - last_updated > timedelta(minutes=self._session_timeout):
                    expired_sessions.append(session_id)

            for session_id in expired_sessions:
                del self._sessions[session_id]
                log_info(f"Deleted expired chat session: {session_id}")

            if expired_sessions:
                log_info(f"Deleted {len(expired_sessions)} expired chat sessions")
        except Exception as e:
            log_error(f"Error cleaning up expired sessions: {str(e)}")

    def get_session_count(self) -> int:
        """
        Get number of active sessions

        Returns:
            int: Number of sessions
        """
        return len(self._sessions)

# Default storage implementation
chat_history_storage = InMemoryChatHistoryStorage()
