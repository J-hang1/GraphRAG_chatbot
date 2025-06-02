"""
Mô-đun giả lập OpenCV (cv2) để tránh vấn đề đệ quy khi import
"""
import sys
import numpy as np
import os

# Kiểm tra xem đã có cờ đánh dấu đang tải cv2 chưa
if hasattr(sys, '_cv2_loading'):
    # Nếu đang tải, trả về một mô-đun giả lập
    class MockCV2:
        """Lớp giả lập cv2 với các hàm cơ bản"""

        @staticmethod
        def imread(filename, flags=None):
            """Giả lập đọc ảnh"""
            return np.zeros((100, 100, 3), dtype=np.uint8)

        @staticmethod
        def imdecode(buf, flags):
            """Giả lập giải mã ảnh từ buffer"""
            return np.zeros((100, 100, 3), dtype=np.uint8)

        @staticmethod
        def imwrite(filename, img):
            """Giả lập ghi ảnh"""
            return True

        @staticmethod
        def rectangle(img, pt1, pt2, color, thickness=1):
            """Giả lập vẽ hình chữ nhật"""
            return img

        @staticmethod
        def circle(img, center, radius, color, thickness=1):
            """Giả lập vẽ hình tròn"""
            return img

        @staticmethod
        def putText(img, text, org, fontFace, fontScale, color, thickness=1):
            """Giả lập vẽ văn bản"""
            return img

        @staticmethod
        def VideoCapture(index):
            """Giả lập camera"""
            class MockCapture:
                def read(self):
                    return True, np.zeros((480, 640, 3), dtype=np.uint8)
                def isOpened(self):
                    return True
                def release(self):
                    pass
            return MockCapture()

        @staticmethod
        def destroyAllWindows():
            """Giả lập đóng cửa sổ"""
            pass

        @staticmethod
        def waitKey(delay):
            """Giả lập chờ phím"""
            return 0

        @staticmethod
        def imshow(winname, mat):
            """Giả lập hiển thị ảnh"""
            pass

        # Các hằng số thường dùng
        IMREAD_COLOR = 1
        IMREAD_GRAYSCALE = 0
        FONT_HERSHEY_SIMPLEX = 0
        FONT_HERSHEY_COMPLEX = 1

    # Xuất mô-đun giả lập
    cv2 = MockCV2()

else:
    # Đánh dấu đang tải cv2
    sys._cv2_loading = True

    try:
        # Thử import cv2 thật
        import cv2 as real_cv2
        cv2 = real_cv2
    except ImportError as e:
        print(f"Lỗi khi import cv2: {e}")

        # Nếu không import được, sử dụng mô-đun giả lập
        class MockCV2:
            """Lớp giả lập cv2 với các hàm cơ bản"""

            @staticmethod
            def imread(filename, flags=None):
                """Giả lập đọc ảnh"""
                return np.zeros((100, 100, 3), dtype=np.uint8)

            @staticmethod
            def imdecode(buf, flags):
                """Giả lập giải mã ảnh từ buffer"""
                return np.zeros((100, 100, 3), dtype=np.uint8)

            @staticmethod
            def imwrite(filename, img):
                """Giả lập ghi ảnh"""
                return True

            @staticmethod
            def rectangle(img, pt1, pt2, color, thickness=1):
                """Giả lập vẽ hình chữ nhật"""
                return img

            @staticmethod
            def circle(img, center, radius, color, thickness=1):
                """Giả lập vẽ hình tròn"""
                return img

            @staticmethod
            def putText(img, text, org, fontFace, fontScale, color, thickness=1):
                """Giả lập vẽ văn bản"""
                return img

            @staticmethod
            def VideoCapture(index):
                """Giả lập camera"""
                class MockCapture:
                    def read(self):
                        return True, np.zeros((480, 640, 3), dtype=np.uint8)
                    def isOpened(self):
                        return True
                    def release(self):
                        pass
                return MockCapture()

            @staticmethod
            def destroyAllWindows():
                """Giả lập đóng cửa sổ"""
                pass

            @staticmethod
            def waitKey(delay):
                """Giả lập chờ phím"""
                return 0

            @staticmethod
            def imshow(winname, mat):
                """Giả lập hiển thị ảnh"""
                pass

            # Các hằng số thường dùng
            IMREAD_COLOR = 1
            IMREAD_GRAYSCALE = 0
            FONT_HERSHEY_SIMPLEX = 0
            FONT_HERSHEY_COMPLEX = 1

        cv2 = MockCV2()

    finally:
        # Xóa cờ đánh dấu
        if hasattr(sys, '_cv2_loading'):
            delattr(sys, '_cv2_loading')
