"""
Module xác thực thông tin từ Neo4j
Sử dụng để xác thực tên sản phẩm và danh mục từ database
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from ...neo4j_client.connection import execute_query
from ...utils.logger import log_info, log_error

class DatabaseValidator:
    """
    Lớp xác thực thông tin từ Neo4j
    """
    
    @staticmethod
    def validate_product_names(product_names: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        Xác thực tên sản phẩm từ Neo4j
        
        Args:
            product_names: Dict chứa tên sản phẩm theo ngôn ngữ
            
        Returns:
            Dict chứa tên sản phẩm đã được xác thực
        """
        validated_names = {
            "vi": [],
            "en": []
        }
        
        # Tạo danh sách tất cả tên sản phẩm
        all_names = []
        if "vi" in product_names:
            all_names.extend(product_names["vi"])
        if "en" in product_names:
            all_names.extend(product_names["en"])
            
        if not all_names:
            return validated_names
            
        try:
            # Tạo điều kiện tìm kiếm
            conditions = []
            for name in all_names:
                if name:
                    # Sử dụng regex matching thay vì CONTAINS
                    conditions.append(f'p.name =~ "(?i).*{name}.*"')
                    
            if not conditions:
                return validated_names
                
            # Tạo truy vấn Cypher
            cypher_query = f"""
            MATCH (p:Product)
            WHERE {" OR ".join(conditions)}
            RETURN p.id as id, p.name as name
            LIMIT 10
            """
            
            # Thực thi truy vấn
            results = execute_query(cypher_query)
            
            # Xử lý kết quả
            for record in results:
                product_name = record.get("name", "")
                if product_name:
                    # Phân loại tên sản phẩm theo ngôn ngữ
                    if any(char in "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ" for char in product_name.lower()):
                        if product_name not in validated_names["vi"]:
                            validated_names["vi"].append(product_name)
                    else:
                        if product_name not in validated_names["en"]:
                            validated_names["en"].append(product_name)
            
            log_info(f"Validated product names: {validated_names}")
            return validated_names
            
        except Exception as e:
            log_error(f"Error validating product names: {str(e)}")
            return product_names
    
    @staticmethod
    def validate_category_names(category_names: List[str]) -> List[str]:
        """
        Xác thực tên danh mục từ Neo4j
        
        Args:
            category_names: Danh sách tên danh mục
            
        Returns:
            Danh sách tên danh mục đã được xác thực
        """
        if not category_names:
            return []
            
        try:
            # Tạo điều kiện tìm kiếm
            conditions = []
            for name in category_names:
                if name:
                    # Sử dụng regex matching thay vì CONTAINS
                    conditions.append(f'c.name_cat =~ "(?i).*{name}.*"')
                    
            if not conditions:
                return []
                
            # Tạo truy vấn Cypher
            cypher_query = f"""
            MATCH (c:Category)
            WHERE {" OR ".join(conditions)}
            RETURN c.id as id, c.name_cat as name
            LIMIT 10
            """
            
            # Thực thi truy vấn
            results = execute_query(cypher_query)
            
            # Xử lý kết quả
            validated_names = []
            for record in results:
                category_name = record.get("name", "")
                if category_name and category_name not in validated_names:
                    validated_names.append(category_name)
            
            log_info(f"Validated category names: {validated_names}")
            return validated_names
            
        except Exception as e:
            log_error(f"Error validating category names: {str(e)}")
            return category_names
    
    @staticmethod
    def get_all_categories() -> List[str]:
        """
        Lấy tất cả các danh mục từ Neo4j
        
        Returns:
            List[str]: Danh sách tên danh mục
        """
        try:
            # Tạo truy vấn Cypher
            cypher_query = """
            MATCH (c:Category)
            RETURN c.name_cat as name
            """
            
            # Thực thi truy vấn
            results = execute_query(cypher_query)
            
            # Xử lý kết quả
            category_names = []
            for record in results:
                category_name = record.get("name", "")
                if category_name and category_name not in category_names:
                    category_names.append(category_name)
            
            return category_names
            
        except Exception as e:
            log_error(f"Error getting all categories: {str(e)}")
            return []
    
    @staticmethod
    def extract_category_from_text(text: str) -> Tuple[List[str], float]:
        """
        Trích xuất tên danh mục từ văn bản và xác thực với Neo4j
        
        Args:
            text: Văn bản cần trích xuất
            
        Returns:
            Tuple[List[str], float]: Danh sách tên danh mục và độ tin cậy
        """
        # Chuẩn bị văn bản để tìm kiếm
        text_lower = text.lower()
        
        # Tìm kiếm các mẫu danh mục cụ thể
        category_patterns = [
            r"danh mục\s+(.*?)(?:\s+có|$)",
            r"loại\s+(.*?)(?:\s+có|$)",
            r"nhóm\s+(.*?)(?:\s+có|$)",
            r"category\s+(.*?)(?:\s+has|$)"
        ]
        
        extracted_categories = []
        for pattern in category_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                for match in matches:
                    if match.strip() and match.strip() not in extracted_categories:
                        extracted_categories.append(match.strip())
        
        if extracted_categories:
            # Xác thực các danh mục đã trích xuất
            validated_categories = DatabaseValidator.validate_category_names(extracted_categories)
            return validated_categories, 0.9 if validated_categories else 0.5
        
        # Nếu không tìm thấy mẫu cụ thể, tìm kiếm tất cả các danh mục
        all_categories = DatabaseValidator.get_all_categories()
        found_categories = []
        
        for category in all_categories:
            if category.lower() in text_lower:
                found_categories.append(category)
        
        return found_categories, 0.7 if found_categories else 0.3
