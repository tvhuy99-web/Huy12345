# Thử giao diện với TalkBack

Bản APK thử nghiệm được dựng bằng GitHub Actions và đăng vào mục Releases sau khi kiểm thử tự động và biên dịch thành công.

## Cài đặt

APK dành cho Android 8 trở lên, ARM64. Bản thử có tên hiển thị “Winlator Trợ năng (thử nghiệm)” và dùng chữ ký debug. Android có thể từ chối cập nhật đè bản Winlator đã cài có chữ ký khác. Giữ bản cài và dữ liệu hiện có cho tới khi có phương án sao lưu phù hợp.

## Quy trình thử

1. Bật TalkBack, mở ứng dụng và duyệt menu chính bằng thao tác vuốt.
2. Tạo một môi trường thử; nhập tên, chọn kích thước màn hình và lưu. Duyệt đến từng nút Chạy và Tùy chọn, xác nhận tên môi trường được đọc kèm.
3. Mở quản lý tệp, duyệt thư mục và kiểm tra tên tệp được đọc cùng nút Mở/Tùy chọn. Thử hủy hộp thoại và kiểm tra tiêu điểm trở về vị trí hợp lý.
4. Trong Cài đặt, thử thanh tốc độ/kích thước con trỏ bằng hành động điều chỉnh của TalkBack hoặc phím mũi tên. Kiểm tra giá trị thay đổi và được lưu.
5. Thử các bộ tăng/giảm số, hộp chọn nhiều mục, lựa chọn đồ họa, ô chọn CPU, màu và hình nền. Kiểm tra tên trường, giá trị và trạng thái chọn.
6. Thử tác vụ tải hoặc tạo môi trường. Thông báo tiến trình cần được đọc theo từng khoảng, không chen liên tục vào thao tác.
7. Đổi tên, rồi xóa môi trường thử rỗng. Kiểm tra hộp thoại xác nhận có thể đọc, hủy và kích hoạt bằng TalkBack.

Ghi lại màn hình đang mở, tên điều khiển, nội dung TalkBack đọc và thao tác không thực hiện được nếu gặp lỗi. Khả năng sử dụng thực tế cần thử trên điện thoại; kiểm thử tự động không thay thế bước này.

Phạm vi bản thử là giao diện Android quản lý Winlator. Cửa sổ trình cài đặt Windows bên trong Wine, bố trí nút chơi game trên vùng vẽ và giao diện trong game cần giải pháp trợ năng và đánh giá riêng.
