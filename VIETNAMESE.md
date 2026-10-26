# Giao diện tiếng Việt cho Winlator

Kho làm việc chính là [tvhuy99-web/Huy12345](https://github.com/tvhuy99-web/Huy12345), nhánh `main`.

Mã ứng dụng và hai thành phần đồ họa đã được đưa vào thư mục thường trong cùng kho. Có thể sửa, xem lịch sử và quản lý các thay đổi tại đây.

| Phần cần sửa | Đường dẫn |
| --- | --- |
| Dự án Android, gồm Gradle và mã ứng dụng | [app/](app/) |
| Mã Java của giao diện | [app/app/src/main/java/com/winlator/](app/app/src/main/java/com/winlator/) |
| Chuỗi giao diện tiếng Việt | [app/app/src/main/res/values-vi/strings.xml](app/app/src/main/res/values-vi/strings.xml) |
| Danh sách lựa chọn và nhạc cụ tiếng Việt | [app/app/src/main/res/values-vi/arrays.xml](app/app/src/main/res/values-vi/arrays.xml) |
| Mã đồ họa Gladio | [gladio/](gladio/) |
| Mã đồ họa Vortek | [vortek/](vortek/) |
| Chương trình trợ năng chạy trong Wine | [runtime-accessibility/](runtime-accessibility/) |

Bản dịch gồm 322 chuỗi giao diện chính, 23 nhãn trợ năng bổ sung, các danh sách lựa chọn, hướng dẫn Box64, thông báo và 128 tên nhạc cụ General MIDI. Các tên công nghệ, tên phím tiêu chuẩn và giá trị cấu hình dùng làm mã định danh được giữ nguyên khi cần.

Trong bản ứng dụng được biên dịch từ mã này, chọn **Cài đặt → Ngôn ngữ → Tiếng Việt**, lưu thay đổi và chấp nhận khởi động lại ứng dụng. Máy dùng tiếng Việt làm ngôn ngữ hệ thống cũng có thể dùng tài nguyên tiếng Việt mặc định.

Cấu trúc đường dẫn bên trong các dự án, nội dung mã và quyền thực thi đã được giữ theo các bản nguồn ghi trong [SOURCE_ORIGINS.md](SOURCE_ORIGINS.md). Khi lấy cập nhật từ dự án gốc, cần ghép các thay đổi vào các thư mục tương ứng.

Đã bổ sung nhãn cho 70 nút biểu tượng và liên kết 67 cặp nhãn–trường. Thanh chỉnh giá trị và bộ tăng/giảm số hỗ trợ thao tác trợ năng và bàn phím; danh sách có nhãn cung cấp cả giá trị hiện tại. Hộp thoại và popup hỗ trợ tiêu điểm, trạng thái tải được thông báo theo khoảng.

Đã kiểm tra cấu trúc XML, ký hiệu định dạng và các danh sách; 5 kiểm thử tự động của điều khiển đã qua. APK thử nghiệm được dựng bằng GitHub Actions và đăng tại [Releases](https://github.com/tvhuy99-web/Huy12345/releases). Cần tiếp tục [thử TalkBack trên điện thoại](ACCESSIBILITY_TESTING.md); chưa có kết quả kiểm thử thiết bị thực tế.

Giai đoạn 2 bổ sung cầu nối thử nghiệm **MSAA + Win32 → bảng Android → thao tác ngược vào Wine**. Mã chương trình hỗ trợ, kiểm thử Wine và giao diện Android được lưu trong cùng kho. Đọc [RUNTIME_ACCESSIBILITY.md](RUNTIME_ACCESSIBILITY.md) trước khi thử; không đồng nhất kết quả cửa sổ mẫu với mức hỗ trợ mọi ứng dụng và game.
