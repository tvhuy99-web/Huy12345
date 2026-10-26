# Bản vá giao diện tiếng Việt cho Winlator

Bản vá này áp dụng cho kho `brunodev85/winlator-app` tại commit `a030f552f452158a2db64fdb32b490fa19c0b48d`, đúng với commit mà thư mục `app` trong kho này đang tham chiếu.

Bản dịch gồm giao diện Android, lựa chọn ngôn ngữ Tiếng Việt, thông báo, phần công trạng và 128 tên nhạc cụ MIDI. Các giá trị lựa chọn được lưu bằng vị trí hoặc giữ nguyên tên kỹ thuật để không làm đổi cấu hình game.

Để áp dụng trong checkout của kho này, khởi tạo submodule rồi chạy từ thư mục gốc:

```sh
git submodule update --init app
git -C app apply ../patches/winlator-vietnamese.patch
```

Sau đó cần lưu commit ứng dụng vào một kho `winlator-app` do bạn quản lý và cập nhật liên kết submodule trong `.gitmodules` cùng gitlink `app`. Kho này hiện vẫn trỏ tới kho ứng dụng upstream nên bản dịch chưa được đóng gói vào APK.
