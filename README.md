# GraphRAG Chatbot

GraphRAG Chatbot là một hệ thống chatbot sử dụng mô hình Retrieval-Augmented Generation (RAG) kết hợp với cơ sở tri thức dạng đồ thị (graph) để cung cấp câu trả lời thông minh, có bối cảnh, và chính xác hơn dựa trên lịch sử trò chuyện, dữ liệu nội bộ cùng các nguồn kiến thức mở rộng.

## Mục đích

- Tăng khả năng hiểu ngữ cảnh của chatbot nhờ lưu trữ và phân tích lịch sử hội thoại.
- Kết nối và truy vấn dữ liệu từ nguồn đồ thị (graph database) nhằm nâng cao chất lượng trả lời.
- Tối ưu hóa trải nghiệm người dùng nhờ khả năng tùy biến ngữ cảnh và tích hợp nhiều agent thông minh.

## Kiến trúc & Thành phần chính

- **ChatHistory Agent:** Quản lý, lưu trữ và phân tích lịch sử trò chuyện. Trích xuất ngữ cảnh phù hợp để bổ sung vào các truy vấn mới.
- **GraphRAG Agent:** Xử lý truy vấn người dùng bằng cách sử dụng ngữ cảnh từ ChatHistory Agent kết hợp truy xuất và tổng hợp thông tin từ graph database.
- **Các thành phần hỗ trợ:** Bao gồm các module lưu trữ tạm thời, phân tích lịch sử, định dạng dữ liệu cho LLM, và giao tiếp với các agent khác.

## Cài đặt

1. **Clone repository về máy:**
   ```bash
   git clone https://github.com/J-hang1/GraphRAG_chatbot.git
   cd GraphRAG_chatbot
   ```

2. **Cài đặt các dependencies (Python):**
   ```bash
   pip install -r requirements.txt
   ```

## Hướng dẫn sử dụng

- Chi tiết cách sử dụng từng agent và chức năng cụ thể nằm trong các thư mục như `app/agents/chathistory_agent/README.md`.
- Bạn có thể khởi tạo và sử dụng các agent theo ví dụ trong tài liệu con để lưu và truy xuất lịch sử chat, trích xuất ngữ cảnh, và tích hợp trả lời từ graph database.

## Đóng góp

Đóng góp của bạn luôn được hoan nghênh! Vui lòng tạo issue hoặc gửi pull request nếu bạn có đề xuất cải thiện dự án.

## Giấy phép

Dự án này được phát hành theo giấy phép MIT.

---

**Tài liệu chi tiết hơn về từng agent, cấu trúc thư mục, ví dụ sử dụng,... vui lòng xem trong các file README.md nhỏ trong từng thư mục con.**
