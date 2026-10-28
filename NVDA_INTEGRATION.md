# NVDA tự khởi động cùng môi trường — bản thử nghiệm

Bản này tích hợp NVDA 2026.3 vào APK. Mặc định, khi máy chủ lệnh của Wine đã sẵn sàng, Winlator chuẩn bị gói NVDA và khởi chạy NVDA. Không cần tự mở trình cài đặt Windows hay tải thêm tệp trên điện thoại.

## Sử dụng

1. Cài bản APK NVDA thử nghiệm trong [Releases](https://github.com/tvhuy99-web/Huy12345/releases). Android 8 trở lên, ARM64. Nếu báo khác chữ ký với bản đang dùng, giữ và sao lưu dữ liệu trước khi thay bản cài.
2. Để trống khoảng **400 MB** cho lần giải nén đầu, rồi khởi động môi trường. Những lần sau tái sử dụng gói đã giải nén.
3. Khi NVDA khởi tạo được, phần mở rộng đi kèm yêu cầu **chính NVDA** đọc câu “NVDA đã khởi động…”. Giọng mặc định là eSpeak NG tiếng Việt. Winlator chỉ báo sẵn sàng khi nhận được nhịp hoạt động do NVDA gửi, không dựa vào việc đã gửi lệnh mở tệp.
4. Nút **NVDA và trợ năng Windows** hoặc mục **Trình đọc màn hình NVDA** trong menu mở bảng điều khiển: Khởi động, Dừng, Khởi động lại; đọc tiêu điểm/cửa sổ; Tab, Shift+Tab, Enter, phím cách và mũi tên. Các nút này gửi phím vào Wine. TalkBack tiếp tục điều khiển giao diện Android.
5. Tắt **Tự khởi động NVDA cùng môi trường** trong Cài đặt hoặc trong bảng NVDA nếu không muốn tự chạy ở phiên sau. Nút Dừng tác động tới phiên hiện tại.
6. **Mở danh sách trợ năng Windows** vẫn cung cấp cầu nối đã có làm đường dự phòng. Khi bật tự chạy NVDA, Winlator không tự mở bảng danh sách này che desktop; vẫn có thể mở bằng tay.

Cử chỉ TalkBack chưa được chuyển thành cử chỉ chạm NVDA. Để điều hướng trong Wine trên điện thoại, dùng các nút gửi phím hoặc bàn phím ngoài.

## Cách tích hợp và giới hạn

- Gói gốc lấy từ NV Access, phiên bản cố định 2026.3, SHA-256 `a8a87cb823da0c62cfbae4a444ae5ae238d54dc82ad6d46d3fdb3fef082799b2`. Không dùng tệp tải về khi mã kiểm tra không khớp.
- Gói portable dùng `nvda_noUIAccess.exe` làm `nvda.exe`, tương ứng cách tạo portable của NVDA. Giữ các thành phần tiếng Việt, giọng eSpeak, thư viện và giấy phép trong gói.
- Bộ khởi chạy cung cấp các đầu vào/đầu ra Windows hợp lệ cho Python nhúng. Lỗi tiến trình NVDA không được coi là đã khởi tạo thành công.
- Wine 10.10 thiếu một số hàm mà NVDA 2026.3 nạp ngay lúc nhập mô-đun `winBindings.kernel32` và `winBindings.user32`. Bản tương thích chỉ trì hoãn lỗi đối với **hàm chưa tồn tại** đến lúc thật sự gọi nó; khi đó vẫn báo `WinError 120` (không hỗ trợ). Hàm có sẵn giữ nguyên cách gọi. Không tạo thông tin MSAA/UIA giả, không mô phỏng kết quả thành công cho hàm thiếu.
- Mã mô-đun NVDA đã sửa nằm trong `source/winBindings/kernel32.py` và `source/winBindings/user32.py` của gói portable. Giấy phép gốc nằm trong `documentation/copying.txt` và tệp `NVDA-COPYING.txt` đi kèm APK. [Mã gốc cố định](https://github.com/nvaccess/nvda/tree/7eb1738dd1556775145453fdd8b6b7ca6b397693), [cách tạo bản tương thích](runtime-nvda/compat.py), [mã phần tích hợp](runtime-nvda/).
- Cấu hình người dùng nằm riêng trong `C:\winlator-nvda\config`; cập nhật bộ chương trình không ghi đè cấu hình này. Gói chương trình được kiểm tra SHA-256 và giải nén vào thư mục tạm trước khi đưa vào sử dụng.
- Phần mở rộng NVDA chỉ ghi trạng thái sẵn sàng, mã tiến trình và thời gian hoạt động. Không lưu văn bản mà NVDA đọc. Khi chạy trên điện thoại, NVDA được gọi với `--no-logging`.
- NVDA phát tiếng không đồng nghĩa đọc đầy đủ mọi ứng dụng. Thông tin trợ năng và sự kiện tiêu điểm vẫn phụ thuộc Wine và từng phần mềm. Chưa có kiểm thử NVDA trên điện thoại Wine/Box64 của người dùng; kết quả máy Linux không thay thế bước đó.

## Kiểm tra trước khi phát hành

Workflow dựng APK phải kiểm tra gói, chạy cửa sổ Windows thật của cầu nối cũ, chạy **NVDA thật** trong Wine, nhận trạng thái từ NVDA và thu được tín hiệu âm thanh ở đầu ra thử nghiệm. Sau đó mới chạy kiểm thử Android, xác minh gói NVDA trong APK và kiểm tra chữ ký. Workflow dò tương thích riêng có thể hoàn tất dù NVDA không khởi tạo; phải đọc trường `ready` trong kết quả, không coi dấu xanh của workflow dò là NVDA đã hoạt động.

Nhật ký và âm thanh của bài thử chỉ dùng dữ liệu thử nghiệm. Người dùng không cần gửi mật khẩu hoặc nhật ký có nội dung riêng tư để báo lỗi; có thể báo câu trạng thái trong bảng NVDA và ứng dụng Windows đang mở.
