# Thử sửa mã tiếng Trung của Zetianji trên Winlator (31/10/2026)

## Mục đích
Nhật ký OnePlus / APK 52 ghi `GetACP=1252`, `GetOEMCP=437` và LCID 1033 trong khi game chứa văn bản GBK. Bản thử này bổ sung cấu hình locale tiếng Trung giản thể riêng cho **một môi trường Winlator**, không đổi ngôn ngữ Android, không tích hợp trực tiếp các DLL của Locale Emulator trên PC và không động đến bản vá CPU 52.

## Cách bật và thử
1. Cài APK **được biên dịch từ nhánh này** (APK 52 hiện tại chưa chứa tính năng).
2. Đóng toàn bộ môi trường Windows/Winlator; sao lưu dữ liệu môi trường quan trọng.
3. Mở **Môi trường → Sửa → Cấu hình Wine → Ngôn ngữ ứng dụng Windows (Wine locale)**.
4. Chọn **Tiếng Trung giản thể (Trung Quốc) - CP936**, lưu cấu hình rồi khởi động lại môi trường hoàn toàn.
5. Khởi chạy Zetianji đã áp dụng bản vá CPU 52. Ghi lại nhật ký **Chẩn đoán game** và thao tác NVDA đọc nội dung.
6. Đối chiếu: `codePages.ansi` phải là **936**, `systemLCID/userLCID` nên là **2052**, GDI phải hiển thị chữ Trung đúng, NVDA phải nhận được chuỗi tiếng Trung thay vì dấu lạ. Cũng kiểm tra game có gọi `xyttsSpeak` hay không.

## Giới hạn
- Đây là bản sửa **chưa được xác minh trên thiết bị**. Đặt `LC_ALL=zh_CN.UTF-8` chưa bảo đảm Wine trên Android/Bionic chuyển `GetACP` sang 936; cần đo trong nhật ký. Trong trường hợp `GetACP` vẫn 1252, sẽ cần điều tra sâu hơn ở tầng khởi tạo locale trong Wine/Proton và GDI.
- Cài đặt được giới hạn theo từng môi trường; biến `LC_ALL`/`LANG` tùy chỉnh trong tab biến môi trường sẽ được ưu tiên. Cấu hình font ANSI được ghi vào registry Wine riêng của môi trường và lưu giá trị cũ để khôi phục khi tắt lựa chọn.
- Không thay đổi/cài đặt file EXE, DLL của game, không sửa cơ chế sao lưu/khôi phục bản vá CPU.

## Hoàn tác
Chọn **Mặc định (theo Winlator)**, lưu và thoát hoàn toàn rồi khởi động lại môi trường. Phần mềm sẽ cố gắng khôi phục cài đặt `ANSI(00)` đã lưu nếu giá trị hiện tại vẫn là giá trị bản thử thiết lập; nếu được thay bởi phần mềm khác thì không ghi đè.

## Kiểm thử cần chạy trên GitHub Actions
- Biên dịch Android và kiểm tra resource/Java.
- Kiểm thử đọc tiếng Trung trong Wine với cả lựa chọn mặc định và CP936.
- Thử nhập liệu/cử chỉ và đường đọc NVDA, bảo đảm các thao tác của APK 52 không hồi quy.
- Chưa khẳng định APK được xây dựng và kiểm thử xong cho đến khi GitHub Actions báo kết quả.
