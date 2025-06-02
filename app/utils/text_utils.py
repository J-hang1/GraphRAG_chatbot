from typing import Dict, List, Optional
import re
import string
import unicodedata

class EntityExtractor:
    """Trích xuất entities từ text sử dụng rule-based matching"""
    
    def __init__(self):
        # Định nghĩa các pattern cho từng loại entity
        self.patterns = {
            'product': [
                r'(về|mua|thông tin|giá) (của )?(?P<product>[\w\s]+)',
                r'(?P<product>cà phê|trà|nước|đồ uống)[\w\s]*'
            ],
            'category': [
                r'(danh mục|loại) (?P<category>[\w\s]+)',
                r'(các|những) (?P<category>[\w\s]+) (hiện có|đang bán)'
            ],
            'price': [
                r'(?P<price>\d+)[k\s]*(đồng|VND|nghìn|ngàn)',
                r'(giá|khoảng) (?P<price>\d+)'
            ],
            'quantity': [
                r'(?P<quantity>\d+)\s*(ly|cốc|chai|lon)',
                r'(số lượng|mua) (?P<quantity>\d+)'
            ]
        }
        self.patterns = {
            key: [re.compile(p, re.IGNORECASE) for p in patterns]
            for key, patterns in self.patterns.items()
        }
        
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Trích xuất các entity từ text
        
        Args:
            text: Text cần trích xuất
            
        Returns:
            Dict với key là loại entity và value là list các entity tìm thấy
        """
        entities = {
            'product': [],
            'category': [],
            'price': [],
            'quantity': []
        }
        
        for entity_type, patterns in self.patterns.items():
            for pattern in patterns:
                matches = pattern.finditer(text)
                for match in matches:
                    if entity_type in match.groupdict():
                        value = match.group(entity_type).strip()
                        if value and value not in entities[entity_type]:
                            entities[entity_type].append(value)
                            
        return entities
    
    def clean_entity(self, entity: str, entity_type: str) -> str:
        """Làm sạch giá trị của entity"""
        if entity_type == 'product':
            # Loại bỏ các từ stop word
            stop_words = ['về', 'mua', 'thông tin', 'giá', 'của']
            for word in stop_words:
                entity = entity.replace(word, '').strip()
                
        elif entity_type == 'price':
            # Chuyển đổi về định dạng số
            entity = re.sub(r'[^\d]', '', entity)
            
        elif entity_type == 'quantity':
            # Chỉ giữ lại số
            entity = re.sub(r'[^\d]', '', entity)
            
        return entity
    
    def get_main_entity(self, entities: Dict[str, List[str]], 
                       entity_type: str) -> Optional[str]:
        """Lấy entity chính của một loại"""
        if entity_type in entities and entities[entity_type]:
            # Lấy entity đầu tiên và làm sạch
            main_entity = entities[entity_type][0]
            return self.clean_entity(main_entity, entity_type)
        return None

# Singleton instance
entity_extractor = EntityExtractor()

def normalize_text(text):
    """
    Normalize text by removing accents, converting to lowercase, and removing special characters
    
    Args:
        text (str): Input text
        
    Returns:
        str: Normalized text
    """
    # Convert to lowercase
    text = text.lower()
    
    # Remove accents
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    
    # Remove special characters
    text = re.sub(r'[^\w\s]', '', text)
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    return text

def extract_keywords(text, min_length=3):
    """
    Extract keywords from text
    
    Args:
        text (str): Input text
        min_length (int, optional): Minimum keyword length
        
    Returns:
        list: List of keywords
    """
    # Normalize text
    normalized_text = normalize_text(text)
    
    # Split into words
    words = normalized_text.split()
    
    # Filter out short words and common stopwords
    stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'if', 'then', 'else', 'when', 'at', 'from', 'by', 'for', 'with', 'about', 'to', 'in', 'on', 'of'}
    keywords = [word for word in words if len(word) >= min_length and word not in stopwords]
    
    return keywords

def calculate_similarity(text1, text2):
    """
    Calculate similarity between two texts using Jaccard similarity
    
    Args:
        text1 (str): First text
        text2 (str): Second text
        
    Returns:
        float: Similarity score (0-1)
    """
    # Extract keywords
    keywords1 = set(extract_keywords(text1))
    keywords2 = set(extract_keywords(text2))
    
    # Calculate Jaccard similarity
    if not keywords1 or not keywords2:
        return 0.0
    
    intersection = keywords1.intersection(keywords2)
    union = keywords1.union(keywords2)
    
    return len(intersection) / len(union)

def summarize_text(text, max_length=100):
    """
    Summarize text by truncating to a maximum length
    
    Args:
        text (str): Input text
        max_length (int, optional): Maximum summary length
        
    Returns:
        str: Summarized text
    """
    if len(text) <= max_length:
        return text
    
    # Truncate to the last complete sentence within max_length
    truncated = text[:max_length]
    last_period = truncated.rfind('.')
    
    if last_period > 0:
        return truncated[:last_period + 1]
    else:
        return truncated + '...'
