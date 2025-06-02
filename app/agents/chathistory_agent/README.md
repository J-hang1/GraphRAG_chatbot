# ChatHistory Agent

## Tổng quan
ChatHistory Agent là một thành phần quan trọng trong hệ thống, chịu trách nhiệm quản lý và phân tích lịch sử trò chuyện giữa người dùng và hệ thống. Agent này cung cấp khả năng lưu trữ, truy xuất và trích xuất ngữ cảnh từ lịch sử chat, giúp các agent khác (như GraphRAG Agent) hiểu được ngữ cảnh của cuộc trò chuyện và đưa ra phản hồi phù hợp.

## Chức năng chính
- Lưu trữ lịch sử chat trong bộ nhớ
- Truy xuất lịch sử chat theo session ID
- Trích xuất ngữ cảnh từ lịch sử chat bằng LLM
- Phân tích lịch sử chat để tìm thông tin hữu ích
- Định dạng lịch sử chat cho LLM và hiển thị

## Cấu trúc thư mục
```
chathistory_agent/
├── __init__.py              # File khởi tạo package
├── logic.py                 # Chứa lớp ChatHistoryAgent với các phương thức chính
├── history_analyzer.py      # Phân tích lịch sử chat bằng cách tìm từ khóa
├── context_extractor.py     # Trích xuất ngữ cảnh từ lịch sử chat bằng LLM
├── storage.py               # Lưu trữ lịch sử chat trong bộ nhớ
├── formatter.py             # Định dạng lịch sử chat cho LLM và hiển thị
└── README.md                # Tài liệu hướng dẫn
```

## Các lớp và phương thức chính

### ChatHistoryAgent (logic.py)
Lớp chính để tương tác với lịch sử chat.

```python
# Khởi tạo agent
agent = ChatHistoryAgent()

# Thêm tin nhắn vào lịch sử chat
agent.add_message(session_id, user_message, bot_response, query_details)

# Lấy lịch sử chat
chat_history = agent.get_chat_history(session_id)

# Trích xuất ngữ cảnh từ lịch sử chat
context = agent.extract_context_from_history(session_id, current_query)

# Đặt lại phiên chat
agent.reset_session(session_id)
```

### InMemoryChatHistoryStorage (storage.py)
Lớp để lưu trữ lịch sử chat trong bộ nhớ.

```python
# Lấy session data
session_data = chat_history_storage.get_session(session_id)

# Thêm tin nhắn
chat_history_storage.add_message(session_id, user_message, bot_response, query_details)

# Cập nhật phản hồi của bot
chat_history_storage.update_bot_response(session_id, bot_response)

# Lấy lịch sử chat
chat_history = chat_history_storage.get_chat_history(session_id)

# Đặt thông tin khách hàng
chat_history_storage.set_customer_info(session_id, customer_id, is_authenticated)
```

### Context Extraction (context_extractor.py)
Các hàm để trích xuất ngữ cảnh từ lịch sử chat.

```python
# Trích xuất ngữ cảnh từ lịch sử chat
context = extract_context_from_history(chat_history, current_query)

# Tạo prompt để trích xuất ngữ cảnh
prompt = create_context_extraction_prompt(history_text, current_query)

# Bổ sung ngữ cảnh vào câu truy vấn
enhanced_query = enhance_query_with_context(query, context)
```

### History Analysis (history_analyzer.py)
Các hàm để phân tích lịch sử chat.

```python
# Phân tích lịch sử chat
analysis = analyze_chat_history(chat_history)

# Tạo phản hồi từ kết quả phân tích
response = format_analysis_response(analysis)
```

### Formatting (formatter.py)
Các phương thức để định dạng lịch sử chat.

```python
# Định dạng lịch sử chat cho LLM
llm_format = chat_history_formatter.format_for_llm(chat_history)

# Định dạng lịch sử chat để hiển thị
display_format = chat_history_formatter.format_for_display(chat_history)

# Định dạng kết quả phân tích
analysis_response = chat_history_formatter.format_analysis_response(analysis)
```

## Cách sử dụng

### Khởi tạo và thêm tin nhắn
```python
from app.agents.chathistory_agent.logic import ChatHistoryAgent

# Khởi tạo agent
chat_history_agent = ChatHistoryAgent()

# Thêm tin nhắn người dùng
session_id = "user123"
user_message = "Tôi muốn tìm cà phê không đường"
chat_history_agent.add_message(session_id, user_message)

# Thêm phản hồi của bot
bot_response = "Chúng tôi có Brewed Coffee không đường. Bạn có muốn thử không?"
query_details = {
    "structured_query": {"intent": "Tìm đồ uống", "filters": {"sugars_g": "= 0"}},
    "selected_products": ["Brewed Coffee"]
}
chat_history_agent.add_message(session_id, user_message, bot_response, query_details)
```

### Trích xuất ngữ cảnh
```python
# Trích xuất ngữ cảnh từ lịch sử chat
current_query = "loại nào trong đó là rẻ nhất"
context = chat_history_agent.extract_context_from_history(session_id, current_query)

# Sử dụng ngữ cảnh trong GraphRAG Agent
graphrag_response = graphrag_agent.process_query(current_query, context)
```

## Lưu ý quan trọng
1. ChatHistory Agent chỉ lưu trữ lịch sử chat trong bộ nhớ, không lưu trữ trong cơ sở dữ liệu.
2. Mặc định, mỗi phiên chat sẽ lưu trữ tối đa 5 tin nhắn gần nhất.
3. Phiên chat sẽ tự động hết hạn sau 30 phút không hoạt động.
4. Khi trích xuất ngữ cảnh, ChatHistory Agent sẽ sử dụng LLM để phân tích lịch sử chat. Nếu LLM không hoạt động, agent sẽ sử dụng phân tích đơn giản bằng cách tìm từ khóa.
5. ChatHistory Agent không lưu trữ câu truy vấn Cypher và kết quả truy vấn, chỉ lưu trữ structured_query và selected_products.

## Tích hợp với các Agent khác
ChatHistory Agent được thiết kế để tích hợp với các agent khác trong hệ thống, đặc biệt là GraphRAG Agent. Khi người dùng gửi một câu hỏi mới, GraphRAG Agent sẽ yêu cầu ChatHistory Agent trích xuất ngữ cảnh từ lịch sử chat để hiểu rõ hơn về ý định của người dùng.

```python
# Trong GraphRAG Agent
def process_query(self, query, session_id):
    # Lấy ngữ cảnh từ ChatHistory Agent
    context = chat_history_agent.extract_context_from_history(session_id, query)
    
    # Sử dụng ngữ cảnh để xử lý câu hỏi
    # ...
    
    # Thêm phản hồi vào lịch sử chat
    chat_history_agent.add_message(session_id, query, response, query_details)
    
    return response
```
