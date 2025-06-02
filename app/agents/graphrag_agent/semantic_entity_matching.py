"""
Module cung cấp các chức năng so sánh ngữ nghĩa giữa thực thể và từ khóa
"""
import numpy as np
from typing import List, Dict, Any, Tuple, Optional, Union
from sklearn.metrics.pairwise import cosine_similarity
import logging

from app.utils.logger import log_info, log_error
from ..core.core_functions import compute_entity_semantic_similarity, get_phobert_manager
from ...neo4j_client.connection import execute_query
from ..core.constants import QUERY_TEMPLATES

# Ngưỡng tương đồng ngữ nghĩa
SEMANTIC_SIMILARITY_THRESHOLD = 0.6

# Từ điển đồng nghĩa và biến thể
SEMANTIC_EQUIVALENTS = {
    "cà phê": ["cafe", "coffee", "espresso", "cappuccino", "latte"],
    "ít đường": ["ít ngọt", "không ngọt", "giảm đường", "low sugar"],
    "sữa": ["milk", "cream", "dairy", "kem sữa", "sữa tươi"],
    "espresso": ["cà phê espresso", "espresso coffee", "cà phê đậm đặc"],
    "ngọt": ["đường", "sugar", "sweet"],
    "đắng": ["bitter", "strong", "mạnh"],
    # Thêm các từ khóa khác...
}

def enhance_keywords_for_entity_matching(keywords: List[str]) -> List[str]:
    """
    Mở rộng và cải thiện danh sách từ khóa cho việc so sánh thực thể

    Args:
        keywords: Danh sách từ khóa ban đầu

    Returns:
        Danh sách từ khóa đã được mở rộng
    """
    enhanced_keywords = []
    for keyword in keywords:
        enhanced_keywords.append(keyword)
        # Thêm các từ đồng nghĩa và biến thể
        for key, equivalents in SEMANTIC_EQUIVALENTS.items():
            if keyword.lower() in key.lower() or any(keyword.lower() in eq.lower() for eq in equivalents):
                enhanced_keywords.extend(equivalents)
                enhanced_keywords.append(key)

    # Loại bỏ các từ khóa trùng lặp và chuẩn hóa
    return list(set([k.lower().strip() for k in enhanced_keywords]))

# Function moved to core_functions.py

def compute_entity_semantic_scores(entity: Dict[str, Any], keywords: List[str]) -> Dict[str, float]:
    """
    Tính toán điểm số ngữ nghĩa cho một thực thể với nhiều từ khóa

    Args:
        entity: Thông tin về thực thể
        keywords: Danh sách từ khóa

    Returns:
        Dictionary chứa điểm số cho mỗi từ khóa và điểm tổng
    """
    entity_name = entity.get("name", "")
    entity_type = entity.get("type", "")
    entity_original_name = entity.get("original_name", "")

    # Tạo văn bản thực thể
    entity_texts = []
    if entity_name:
        entity_texts.append(entity_name)
    if entity_type:
        entity_texts.append(entity_type)
    if entity_original_name and entity_original_name != entity_name:
        entity_texts.append(entity_original_name)

    entity_text = " ".join(entity_texts)

    # Tính toán điểm số cho mỗi từ khóa
    scores = {}
    max_score = 0
    max_keyword = ""

    for keyword in keywords:
        score = compute_entity_semantic_similarity(entity_text, keyword)
        scores[keyword] = score

        if score > max_score:
            max_score = score
            max_keyword = keyword

    # Thêm điểm tổng và từ khóa tốt nhất
    scores["max_score"] = max_score
    scores["max_keyword"] = max_keyword
    scores["is_match"] = max_score >= SEMANTIC_SIMILARITY_THRESHOLD

    return scores

def find_matching_entities_semantic(entities: List[Dict[str, Any]], keywords: List[str]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Tìm các thực thể khớp với từ khóa dựa trên độ tương đồng ngữ nghĩa

    Args:
        entities: Danh sách thực thể
        keywords: Danh sách từ khóa

    Returns:
        Tuple chứa danh sách thực thể khớp và số lượng thực thể khớp
    """
    # Mở rộng danh sách từ khóa
    enhanced_keywords = enhance_keywords_for_entity_matching(keywords)
    log_info(f"Danh sách từ khóa đã được mở rộng: {enhanced_keywords}")

    matching_entities = []
    matching_count = 0

    for entity in entities:
        # Tính toán điểm số ngữ nghĩa
        semantic_scores = compute_entity_semantic_scores(entity, enhanced_keywords)

        # Thêm điểm số vào thực thể
        entity["semantic_scores"] = semantic_scores

        # Kiểm tra xem thực thể có khớp không
        if semantic_scores["is_match"]:
            matching_count += 1
            matching_entities.append(entity)

    return matching_entities, matching_count

def post_process_with_semantic_similarity(results: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Hậu xử lý kết quả với độ tương đồng ngữ nghĩa

    Args:
        results: Danh sách kết quả từ truy vấn Neo4j
        keywords: Danh sách từ khóa

    Returns:
        Danh sách kết quả đã được xử lý
    """
    # Mở rộng danh sách từ khóa
    enhanced_keywords = enhance_keywords_for_entity_matching(keywords)

    # Lấy PhoBERT manager
    phobert_manager = get_phobert_manager()

    # Đảm bảo PhoBERT đã được tải
    if not phobert_manager.is_loaded and not phobert_manager.wait_for_model(timeout=30):
        log_error("Không thể tải PhoBERT model để hậu xử lý kết quả")
        return results

    # Xử lý từng kết quả
    for result in results:
        # Lấy thông tin sản phẩm
        product_name = result.get("product_name", "")
        product_description = result.get("product_description", "")

        # Tạo văn bản sản phẩm
        product_text = f"{product_name} {product_description}".strip()

        # Tính toán điểm số ngữ nghĩa cho sản phẩm
        semantic_scores = {}
        total_semantic_score = 0

        for keyword in enhanced_keywords:
            score = compute_entity_semantic_similarity(product_text, keyword)
            semantic_scores[keyword] = score
            total_semantic_score += score

        # Thêm điểm số ngữ nghĩa vào kết quả
        result["semantic_scores"] = semantic_scores
        result["semantic_total_score"] = total_semantic_score

        # Kết hợp điểm số ngữ nghĩa với điểm số hiện tại
        current_score = result.get("total_score", 0)
        combined_score = current_score * 0.7 + total_semantic_score * 0.3

        # Cập nhật điểm số
        result["original_score"] = current_score
        result["total_score"] = combined_score

    # Sắp xếp lại kết quả theo điểm số mới
    results.sort(key=lambda x: x.get("total_score", 0), reverse=True)

    return results

class SemanticEntityMatching:
    """Handle semantic entity matching for GraphRAG agent"""
    
    def __init__(self):
        self._logger = logging.getLogger('agent.graphrag.semantic')
        
    def match_entities(self, text: str, entity_type: str) -> List[Dict[str, Any]]:
        """Match entities in text using semantic search"""
        try:
            log_info(f"🔍 Tìm kiếm thực thể loại {entity_type} trong: '{text}'")
            
            # Generate query based on entity type
            query = self._generate_entity_query(entity_type, text)
            if not query:
                return []
                
            # Execute query
            results = execute_query(query)
            
            log_info(f"✅ Tìm thấy {len(results)} thực thể {entity_type}")
            return results
            
        except Exception as e:
            log_error(f"❌ Lỗi khi tìm kiếm thực thể: {str(e)}")
            return []
            
    def match_product_entities(self, text: str) -> List[Dict[str, Any]]:
        """Match product entities in text"""
        return self.match_entities(text, "product")
        
    def match_category_entities(self, text: str) -> List[Dict[str, Any]]:
        """Match category entities in text"""
        return self.match_entities(text, "category")
        
    def match_store_entities(self, text: str) -> List[Dict[str, Any]]:
        """Match store entities in text"""
        return self.match_entities(text, "store")
        
    def _generate_entity_query(self, entity_type: str, text: str) -> Optional[str]:
        """Generate query based on entity type"""
        if entity_type == "product":
            return self._generate_product_query(text)
        elif entity_type == "category":
            return self._generate_category_query(text)
        elif entity_type == "store":
            return self._generate_store_query(text)
        else:
            return None
            
    def _generate_product_query(self, text: str) -> str:
        """Generate product query"""
        return f"""
        MATCH (p:Product)-[:BELONGS_TO_CATEGORY]->(c:Category)
        WHERE p.name =~ "(?i).*{text}.*" OR p.descriptions =~ "(?i).*{text}.*"
        RETURN p.id as product_id, p.name as product_name, p.descriptions as product_description,
               c.id as category_id, c.name_cat as category_name, c.description as category_description
        ORDER BY p.name
        LIMIT 10
        """
        
    def _generate_category_query(self, text: str) -> str:
        """Generate category query"""
        return f"""
        MATCH (c:Category)
        WHERE c.name_cat =~ "(?i).*{text}.*" OR c.description =~ "(?i).*{text}.*"
        RETURN c.id as category_id, c.name_cat as category_name, c.description as category_description
        ORDER BY c.name_cat
        LIMIT 10
        """
        
    def _generate_store_query(self, text: str) -> str:
        """Generate store query"""
        return f"""
        MATCH (s:Store)
        WHERE s.name =~ "(?i).*{text}.*" OR s.address =~ "(?i).*{text}.*"
        RETURN s.id as store_id, s.name as store_name, s.address as store_address,
               s.latitude as latitude, s.longitude as longitude
        ORDER BY s.name
        LIMIT 10
        """
