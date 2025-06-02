"""
Query executor for GraphRAG agent
"""
from typing import Dict, Any, List, Optional, Union
import json
import logging
from ...utils.logger import log_info, log_error
from ...neo4j_client.connection import execute_query
from ..core.constants import TIMEOUT_SETTINGS

class QueryExecutor:
    """Query executor for GraphRAG agent"""
    
    def __init__(self):
        self._logger = logging.getLogger('agent.graphrag.query')
        
    def execute_query(self, cypher_query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute Cypher query"""
        try:
            log_info("🔍 Thực thi câu truy vấn Cypher")
            log_info(f"📝 Query: {cypher_query}")
            if params:
                log_info(f"📝 Params: {json.dumps(params, ensure_ascii=False)}")
                
            # Execute query with timeout
            result = execute_query(
                cypher_query,
                params=params,
                timeout=TIMEOUT_SETTINGS["query"]
            )
            
            log_info(f"✅ Đã thực thi query thành công, kết quả: {len(result)} bản ghi")
            return result
            
        except Exception as e:
            log_error(f"❌ Lỗi khi thực thi query: {str(e)}")
            return []
            
    def execute_batch_query(self, queries: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Execute multiple Cypher queries in batch"""
        try:
            log_info("🔍 Thực thi batch queries")
            log_info(f"📝 Số lượng queries: {len(queries)}")
            
            results = []
            for query_info in queries:
                cypher_query = query_info.get("query")
                params = query_info.get("params")
                
                if not cypher_query:
                    log_error("❌ Query không hợp lệ")
                    continue
                    
                result = self.execute_query(cypher_query, params)
                results.append(result)
                
            log_info(f"✅ Đã thực thi batch queries thành công, kết quả: {len(results)} queries")
            return results
            
        except Exception as e:
            log_error(f"❌ Lỗi khi thực thi batch queries: {str(e)}")
            return []
            
    def execute_transaction(self, queries: List[Dict[str, Any]]) -> bool:
        """Execute multiple Cypher queries in a transaction"""
        try:
            log_info("🔍 Thực thi transaction")
            log_info(f"📝 Số lượng queries: {len(queries)}")
            
            # Start transaction
            self._logger.info("Bắt đầu transaction")
            
            # Execute queries
            for query_info in queries:
                cypher_query = query_info.get("query")
                params = query_info.get("params")
                
                if not cypher_query:
                    log_error("❌ Query không hợp lệ")
                    return False
                    
                result = self.execute_query(cypher_query, params)
                if not result:
                    log_error("❌ Query thất bại")
                    return False
                    
            # Commit transaction
            self._logger.info("Commit transaction")
            
            log_info("✅ Đã thực thi transaction thành công")
            return True
            
        except Exception as e:
            log_error(f"❌ Lỗi khi thực thi transaction: {str(e)}")
            return False
            
    def validate_query(self, cypher_query: str) -> bool:
        """Validate Cypher query"""
        try:
            log_info("🔍 Kiểm tra tính hợp lệ của query")
            
            # Check if query is empty
            if not cypher_query or not cypher_query.strip():
                log_error("❌ Query trống")
                return False
                
            # Check if query starts with MATCH
            if not cypher_query.strip().upper().startswith("MATCH"):
                log_error("❌ Query phải bắt đầu bằng MATCH")
                return False
                
            # Check if query has RETURN clause
            if "RETURN" not in cypher_query.upper():
                log_error("❌ Query phải có mệnh đề RETURN")
                return False
                
            log_info("✅ Query hợp lệ")
            return True
            
        except Exception as e:
            log_error(f"❌ Lỗi khi kiểm tra query: {str(e)}")
            return False 