"""
Prompt templates for GraphRAG agent
"""
from typing import Dict, Any, List, Optional, Union
import json
import logging
from ...utils.logger import log_info, log_error

class PromptTemplates:
    """Prompt templates for GraphRAG agent"""
    
    def __init__(self):
        self._logger = logging.getLogger('agent.graphrag.prompt')
        
    def get_intent_prompt(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Get intent analysis prompt"""
        try:
            log_info("🔍 Tạo prompt phân tích intent")
            
            # Create base prompt
            prompt = self._create_base_prompt(message)
            
            # Add context if available
            if context:
                prompt = self._add_context_to_prompt(prompt, context)
                
            log_info("✅ Đã tạo prompt phân tích intent")
            return prompt
            
        except Exception as e:
            log_error(f"❌ Lỗi khi tạo prompt: {str(e)}")
            return ""
            
    def get_query_prompt(self, intent_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
        """Get query generation prompt"""
        try:
            log_info("🔍 Tạo prompt tạo query")
            
            # Create base prompt
            prompt = self._create_query_prompt(intent_data)
            
            # Add context if available
            if context:
                prompt = self._add_context_to_prompt(prompt, context)
                
            log_info("✅ Đã tạo prompt tạo query")
            return prompt
            
        except Exception as e:
            log_error(f"❌ Lỗi khi tạo prompt: {str(e)}")
            return ""
            
    def get_response_prompt(self, query_result: List[Dict[str, Any]], intent_data: Dict[str, Any]) -> str:
        """Get response generation prompt"""
        try:
            log_info("🔍 Tạo prompt tạo response")
            
            # Create base prompt
            prompt = self._create_response_prompt(query_result, intent_data)
            
            log_info("✅ Đã tạo prompt tạo response")
            return prompt
            
        except Exception as e:
            log_error(f"❌ Lỗi khi tạo prompt: {str(e)}")
            return ""
            
    def _create_base_prompt(self, message: str) -> str:
        """Create base intent analysis prompt"""
        return f"""Bạn là một chuyên gia phân tích intent. Hãy phân tích câu hỏi sau và trả về thông tin intent dưới dạng JSON:

Câu hỏi: {message}

Hãy phân tích và trả về một JSON object với các trường sau:
- query_type: Loại truy vấn (product, category, store)
- intent: Mục đích chính của câu hỏi
- keywords: Danh sách từ khóa quan trọng
- entities: Danh sách thực thể được đề cập
- constraints: Các ràng buộc về giá, đường, caffeine, calories, protein
- sort_by: Tiêu chí sắp xếp (nếu có)
- sort_order: Thứ tự sắp xếp (asc/desc)

Chỉ trả về JSON object, không thêm giải thích hoặc văn bản khác.
"""
        
    def _create_query_prompt(self, intent_data: Dict[str, Any]) -> str:
        """Create query generation prompt"""
        return f"""Bạn là một chuyên gia về Neo4j và Cypher query. Hãy tạo một câu truy vấn Cypher dựa trên thông tin intent sau:

Intent Data:
{json.dumps(intent_data, indent=2, ensure_ascii=False)}

Hãy tạo một câu truy vấn Cypher phù hợp với intent trên. Chỉ trả về câu truy vấn Cypher, không thêm giải thích hoặc văn bản khác.
"""
        
    def _create_response_prompt(self, query_result: List[Dict[str, Any]], intent_data: Dict[str, Any]) -> str:
        """Create response generation prompt"""
        return f"""Bạn là một chuyên gia tư vấn. Hãy tạo một câu trả lời dựa trên kết quả truy vấn và intent sau:

Intent Data:
{json.dumps(intent_data, indent=2, ensure_ascii=False)}

Query Result:
{json.dumps(query_result, indent=2, ensure_ascii=False)}

Hãy tạo một câu trả lời tự nhiên, ngắn gọn và hữu ích. Chỉ trả về câu trả lời, không thêm giải thích hoặc văn bản khác.
"""
        
    def _add_context_to_prompt(self, prompt: str, context: Dict[str, Any]) -> str:
        """Add context to prompt"""
        context_text = "Context:\n\n"
        
        # Add chat history
        if "chat_history" in context:
            chat_history = context["chat_history"]
            context_text += "Chat History:\n"
            for message in chat_history:
                context_text += f"- {message}\n"
                
        # Add user preferences
        if "preferences" in context:
            preferences = context["preferences"]
            context_text += "\nUser Preferences:\n"
            for pref in preferences:
                context_text += f"- {pref}\n"
                
        # Add mentioned entities
        if "mentioned_entities" in context:
            entities = context["mentioned_entities"]
            context_text += "\nMentioned Entities:\n"
            for entity_type, entity_list in entities.items():
                context_text += f"- {entity_type}: {', '.join(entity_list)}\n"
                
        return f"{prompt}\n\n{context_text}"


