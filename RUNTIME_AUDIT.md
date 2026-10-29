# Kết quả mô phỏng trợ năng Winlator — 29/10/2026

**Chưa thể khẳng định đọc được tất cả giao diện Windows.** Lượt mô phỏng mở rộng có **59 kịch bản: 54 đạt, 4 hỗ trợ một phần, 1 còn lỗi**. Không có lỗi trong các trường hợp bắt buộc trước khi dựng APK. Một trường hợp khảo sát trình đơn ứng dụng khác còn lỗi được giữ nguyên trong kết quả, không xóa hoặc tính là đạt.

Mã đã kiểm tra: [05566f7](https://github.com/tvhuy99-web/Huy12345/commit/05566f7bd510e8ee7a0317fe982780125b5f07c9). Hai lượt NVDA độc lập cho cùng kết quả: [kiểm thử trước khi dựng APK](https://github.com/tvhuy99-web/Huy12345/actions/runs/40800425995), [mô phỏng tương thích](https://github.com/tvhuy99-web/Huy12345/actions/runs/40800425915). Tệp chi tiết `runtime-audit.json`, nhật ký và âm thanh thử nằm trong artifact chẩn đoán của từng lượt chạy.

## Đã sửa và kiểm tra được

| Phần giao diện | Kết quả và phạm vi |
| --- | --- |
| Trình đơn NVDA | Đã tái hiện lỗi chỉ đọc “không xác định, đang có focus, ẩn”. Bản sửa đọc và duyệt được **35 nhãn** trong trình đơn và trình đơn con thực tế. Chỉ khảo sát nhãn; không kích hoạt tất cả lệnh như thoát hay khôi phục cấu hình. |
| Cấu hình NVDA | Mở bằng mục Cấu hình thật. Khảo sát **19 nhóm**, **255 lượt điều khiển trong vòng Tab**; đọc nhãn, giá trị hoặc trạng thái hiện tại. Bao gồm nút đánh dấu ba trạng thái đã sửa. Số lượt có tính các nút xác nhận/hủy lặp lại ở mỗi nhóm; không phải 255 điều khiển duy nhất. |
| Chuyển cửa sổ | Đổi giữa WFM và một cửa sổ Win32 thật; chọn từ danh sách cửa sổ và quay về trình quản lý tệp. Chỉ báo đã chuyển sau khi kiểm tra cửa sổ tiền cảnh thật. |
| Ổ đĩa và thư mục | WFM thật: chọn ổ, mở, quay lên Computer, chuyển vùng, mở thư mục và nhập đường dẫn. Tái kiểm tra cả khi chặn hai đường giả lập phím cũ. |
| Các điều khiển Win32 mẫu | Đọc và thao tác danh sách, nút, hộp đánh dấu, ô nhập tiếng Việt, hộp chọn, nút chọn, thanh trượt; không đọc hoặc ghi mật khẩu thử. |
| Hộp thoại xác nhận | Đọc nút hiện tại và hủy được hộp thoại mẫu. Không thay thế việc thử một trình cài đặt game cụ thể. |
| Giọng Android | Driver NVDA thật gửi tiếng Việt, dấu mốc hoàn tất và lệnh ngắt tới đầu nhận mô phỏng. Không có giọng Google/Samsung trên thiết bị trong CI. |

Đường trình đơn, Cấu hình và chuyển cửa sổ được thử khi chặn giả lập phím cũ. Khảo sát các nhóm cài đặt dùng cấu hình eSpeak dự phòng; đường giọng Android được kiểm tra riêng. Việc Tab và đọc được một cài đặt không chứng minh mọi giá trị hoặc mọi tính năng trong nhóm đó hoạt động.

## Những phần chưa đầy đủ

- **Còn lỗi:** tên mục trong trình đơn bật lên của cửa sổ Win32 mẫu chưa đọc được. Trình đơn có mở, nhưng truy vấn danh sách mục trả về lỗi; không coi câu “trình đơn đang mở” là đã đọc được mục.
- **Hỗ trợ một phần:** bài thử không có màn hình nền hoặc nút Start điều khiển được. Đã kiểm tra lời thông báo thiếu chức năng; không tính là đã truy cập được Desktop/Start. Một cửa sổ khay hệ thống có thể vẫn tồn tại mà không có nút Start.
- **Hỗ trợ một phần:** hộp chọn tệp mới khảo sát ô nhập và Tab; chưa xác minh toàn bộ danh sách tệp và các chế độ xem.
- **Hỗ trợ một phần:** điều khiển ứng dụng Windows khác vẫn có trường hợp cần đường bàn phím. Khi cố ý chặn đường đó, danh sách Win32 mẫu không di chuyển; hỗ trợ trực tiếp riêng của WFM/NVDA không tự áp dụng cho mọi ứng dụng.

Chưa thử mọi game, trình cài/gỡ cài đặt, giao diện tự vẽ, đọc liên tục trong mọi ứng dụng, phần cứng cử chỉ hoặc Wine/Box64 trên điện thoại. Môi trường khảo sát là NVDA 2026.3 trong Wine trên Linux với cửa sổ Windows thật. Đây là kết quả mô phỏng, không phải chứng nhận mọi màn hình đã tiếp cận được.

## Tại sao đang ở ổ C

Winlator mở WFM khi khởi động. Computer là trang đầu của trình quản lý tệp, và C là mục đầu tiên được chọn. Từ trong ổ/thư mục, **vuốt trái ba ngón (Backspace)** để lên thư mục cha; từ gốc ổ quay về Computer. Computer không có thư mục cha phía trên.

Để đổi ứng dụng, chạm ba ngón, chọn **Danh sách cửa sổ đang mở**, vuốt chọn và chạm hai lần. Có lựa chọn **Quay về trình quản lý tệp**. Muốn trở về Android, dùng **Thoát môi trường Windows**, xác nhận, rồi tự bật lại TalkBack; thao tác này đóng các ứng dụng Windows.

## Chi tiết nhóm cài đặt NVDA

| Nhóm | Lượt điều khiển qua Tab | Đọc được trong lượt khảo sát |
| --- | ---: | --- |
| Chung | 12 | Có |
| Giọng đọc | 29 | Có |
| Chữ nổi | 29 | Có |
| Âm thanh | 9 | Có |
| Quyền riêng tư và bảo mật | 7 | Có |
| Hỗ trợ nhìn | 7 | Có |
| Kính lúp | 12 | Có |
| Bàn phím | 15 | Có |
| Chuột | 10 | Có |
| Con trỏ duyệt | 7 | Có |
| Phương thức nhập | 8 | Có |
| Trình Bày Đối Tượng | 14 | Có |
| Chế độ duyệt | 15 | Có |
| Định Dạng Tài Liệu | 38 | Có |
| Điều hướng tài liệu | 5 | Có |
| Truy Cập Từ Xa | 4 | Có |
| Toán học | 21 | Có |
| Cửa hàng Add-on | 8 | Có |
| Nâng cao | 5 | Có |

Hướng dẫn cử chỉ và giới hạn: [NVDA_INTEGRATION.md](NVDA_INTEGRATION.md). Mã bài khảo sát: [test_runtime_audit.py](runtime-nvda/test_runtime_audit.py).

