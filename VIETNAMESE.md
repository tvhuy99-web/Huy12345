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

Bản dịch gồm 322 chuỗi giao diện, các danh sách lựa chọn, hướng dẫn Box64, thông báo và 128 tên nhạc cụ General MIDI. Các tên công nghệ, tên phím tiêu chuẩn và giá trị cấu hình dùng làm mã định danh được giữ nguyên khi cần.

Trong bản ứng dụng được biên dịch từ mã này, chọn **Cài đặt → Ngôn ngữ → Tiếng Việt**, lưu thay đổi và chấp nhận khởi động lại ứng dụng. Máy dùng tiếng Việt làm ngôn ngữ hệ thống cũng có thể dùng tài nguyên tiếng Việt mặc định.

Cấu trúc đường dẫn bên trong các dự án, nội dung mã và quyền thực thi đã được giữ theo các bản nguồn ghi trong [SOURCE_ORIGINS.md](SOURCE_ORIGINS.md). Khi lấy cập nhật từ dự án gốc, cần ghép các thay đổi vào các thư mục tương ứng.

Đã kiểm tra cấu trúc XML, độ phủ chuỗi dịch, ký hiệu định dạng và số lượng/thứ tự mục trong các danh sách. Chưa biên dịch APK hoặc chạy kiểm thử trên thiết bị Android. Khả năng thao tác đầy đủ bằng TalkBack cần được kiểm tra và cải thiện riêng.
