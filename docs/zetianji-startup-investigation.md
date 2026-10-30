# Kiểm tra khởi động Zetianji — 30/10/2026

## Phạm vi và kết luận đã kiểm chứng

Đã tải đúng bản game người dùng cung cấp, giải nén bằng mật khẩu được cung cấp,
kiểm tra tệp thực thi và chạy trong các môi trường Wine dùng một lần trên GitHub
Actions. Đây là Wine amd64/i386 trên Ubuntu 24.04, **không phải** OnePlus,
Android hoặc Box64. Kết quả này khoanh vùng lỗi; không chứng minh game đã chạy
được trên điện thoại.

Game có thể hiện cửa sổ và nhận phím Enter trong môi trường mô phỏng. Nội dung
danh sách chuyển từ lời chào sang hướng dẫn âm lượng. Tuy nhiên, lời đọc do game
gửi ra chưa xuất hiện trong NVDA ở các lượt thử với bộ chuyển giọng hiện tại.
Phép thử gọi trực tiếp thư viện NVDA 32 bit **và chính bộ chuyển giọng đi kèm
game** đọc được câu kiểm tra và tạo âm thanh. Vì vậy, không thể quy toàn bộ
hiện tượng cho game bị thoát, NVDA không hoạt động hoặc bộ chuyển giọng hoàn
toàn không tương thích. Chưa xác định chính xác vì sao đường gọi từ game im.

Không thay đổi APK 48 hoặc nhánh chính trong quá trình nghiên cứu này.

## Mẫu được kiểm tra

- Google Drive file ID: `1drjUVlzfTue5eH3azSaCkuuW4IFTwB74`.
- Tệp: `Zetianji (No Binding Required & Customizable Fragments Edition).rar`.
- Kích thước: 1.529.767.694 byte.
- SHA-256: `dc7a617ca3e08e9e9f7d1e3bf6b636534e9e70bc7fee676d6293de506f12d831`.
- `zetianji.exe` là chương trình Windows x86 32 bit, không phải tệp thực thi .NET.
- Không đưa game hoặc DLL của game vào kho mã hay artifact công khai.

## Đối chiếu nhật ký trên điện thoại

Nhật ký APK 48 ghi nhận game được mở lúc 03:47:56 UTC, PID 356. Tiến trình vẫn
chạy hơn 80 giây nhưng các cửa sổ được quan sát đều bị ẩn. Cửa sổ `WTWindow`
mang tiêu đề `冰山文字编辑器` xuất hiện ở cả điện thoại lẫn mô phỏng. Trong mô
phỏng, chính cửa sổ này chứa giao diện lời chào của game; không nên loại nó
chỉ vì tiêu đề giống tên một trình soạn thảo.

Trên điện thoại, cửa sổ đang nhận thao tác vẫn là trình quản lý tệp WFM.
Alt+F4 mở xác nhận đóng WFM, rồi màn hình trở về Desktop trong khi game vẫn
còn chạy. Dòng “Desktop cửa sổ” không đủ để kết luận game đã bị lỗi và thoát.

## Kết quả mô phỏng

| Phép thử | Kết quả quan sát |
| --- | --- |
| Không chạy NVDA | Game thoát với mã 0 trong vài giây ở mẫu thử này. |
| Có NVDA, chặn hoặc cho phép mạng | Game tiếp tục chạy, cửa sổ hiện sau khoảng 4 giây; chưa có lời đọc nội dung game. |
| Đổi mã ký tự ANSI từ 1252 sang 936 | Không khôi phục được lời đọc game. |
| Xóa cấu hình giọng và chọn lại NVDA | Chọn NVDA lưu `engine=3`; game vẫn im. |
| Gửi phím khi chưa đặt đúng X focus | Lệnh gửi phím thành công nhưng không đủ để chứng minh game đã nhận. |
| Đặt focus vào đúng cửa sổ game rồi Enter | Nội dung trong ListBox của game thay đổi sang trang hướng dẫn tiếp theo. |
| Gọi trực tiếp NVDA Controller Client 32 bit | NVDA nhận câu kiểm tra, đọc văn bản thường và SSML; thu được âm thanh thực tế. |
| Gọi trực tiếp `xinyitts.dll` hiện tại | `xyttsInitA`, `xyttsSpeakW` và `xyttsSpeakA` đều trả 1; hai câu kiểm tra xuất hiện thực tế trong nhật ký lời đọc NVDA. |
| Thay bằng bộ DLL cũ trong thư mục `读屏` của game | Đọc được thông báo thiết lập ban đầu nhưng vẫn ở hộp chọn thư viện giọng. Chưa xác nhận cách này đọc được game. |

Nội dung game quan sát được gồm lời chào và hướng dẫn dùng PageUp/PageDown để
điều chỉnh nhạc nền, Shift+PageUp/PageDown cho hiệu ứng, F9 để xem phím tắt.
Đây là nội dung giao diện đọc từ cửa sổ game, không phải câu do bộ thử tự thêm.

Ở lượt thử 7, số mẫu âm thanh hoạt động trong thời gian chỉ chạy game là 0;
sau khi gọi câu kiểm tra NVDA là 78.405. Điều này chứng minh đường âm thanh thử
hoạt động, nhưng chưa xác định chính xác hàm nào trong game làm mất lời đọc.

Lượt thử 8 giữ bộ chuyển giọng hiện tại: game vẫn không phát âm thanh trong
60 giây quan sát. Sau đó, bộ thử gọi trực tiếp `xyttsInitA(NULL, NULL)`,
`xyttsSpeakW` và `xyttsSpeakA` với đúng ABI 32 bit đã kiểm tra. NVDA thực sự
nhận “Kiểm tra trực tiếp bộ chuyển giọng.” và “Voice adapter ASCII check.”;
bộ đếm âm thanh đối chứng có 106.026 mẫu hoạt động, gồm cả các câu thử Controller.
Đây là bằng chứng đường DLL → NVDA có thể hoạt động, không phải bằng chứng
game đã gửi thành công nội dung của nó. Cần theo dõi đường gọi từ game và
cấu hình/game state trước khi kết luận nguyên nhân nội bộ cụ thể.

Hai tình huống bộ đọc cũ (mã ký tự 1252 và 936) vẫn dừng ở cửa sổ ATL
`语音库选择` sau thao tác bàn phím. Không tạo `api.ini`, không quan sát được
lời chào game trong nhật ký NVDA. Âm thanh thu được ở các tình huống này bao
gồm thông báo thiết lập ban đầu; không được dùng nó làm bằng chứng game nói được.

## Những giả thuyết chưa được bằng chứng hỗ trợ

- Không có bằng chứng quy lỗi cho thiếu .NET của tệp thực thi game.
- Không có bằng chứng việc dùng tiếng Trung làm ngôn ngữ hệ thống tự sửa được lỗi.
- Thư viện chuyển giọng ANSI hiện tại dùng mã ký tự hệ thống; không phải chỉ nhận UTF-8.
- Từ điển dịch đi kèm trống; tài liệu đi kèm cho biết lời đọc vẫn hoạt động khi
  không có từ điển. Chưa có bằng chứng từ điển dịch làm mất lời đọc.
- Cảnh báo helper NVDA và các địa chỉ trong ảnh chụp luồng chưa chứng minh được
  game bị treo ở RPC. Địa chỉ ứng viên trên stack không phải call stack hoàn chỉnh.
- Mã trả về thành công của Controller API đơn lẻ chưa đủ: phép thử đối chứng
  không chạy NVDA cũng từng trả 0. Cần đối chiếu PID NVDA, nhật ký câu thực sự
  được nhận và âm thanh thu được.

## Phần cần sửa tiếp trên Winlator

1. Theo dõi cửa sổ thuộc đúng tiến trình game; phân biệt cửa sổ bị ẩn với game
   đã thoát. Chỉ cho hiện/chuyển focus khi nhận diện được cửa sổ ứng dụng có
   nội dung, tránh tự hiện toàn bộ cửa sổ trợ giúp ẩn.
2. Xác minh phím được gửi đến đúng game. Kết quả WFM nhận phím không chứng minh
   game nhận phím; không dùng thay đổi trong trình quản lý tệp làm phản hồi game.
3. Theo dõi riêng khởi tạo bộ giọng, lời đọc được gửi, lời đọc NVDA nhận và lời
   đọc Android thực sự phát. Mã trả về “thành công” cần có bằng chứng tiếp theo.
4. Kiểm tra lại trên điện thoại sau khi có thay đổi cụ thể; kết quả Wine trên
   Linux không thay thế kiểm thử Wine/Box64 trên OnePlus.

## Nguồn kết quả có thể kiểm tra lại

- [Lượt thử 5](https://github.com/tvhuy99-web/Huy12345/actions/runs/41003076430):
  đối chiếu NVDA, mạng và mã ký tự.
- [Lượt thử 6](https://github.com/tvhuy99-web/Huy12345/actions/runs/41005052581):
  đặt lại giọng và kiểm tra âm thanh đối chứng.
- [Lượt thử 7](https://github.com/tvhuy99-web/Huy12345/actions/runs/41006497958):
  đặt đúng focus và xác nhận game chuyển trang sau Enter.
- [Lượt thử 8](https://github.com/tvhuy99-web/Huy12345/actions/runs/41008053919):
  gọi riêng bộ chuyển giọng và kiểm tra lựa chọn thư viện đọc cũ.

Artifact `zetianji-startup-findings` chứa kết quả từng tình huống, cửa sổ và
tiến trình, phím đã gửi, câu NVDA nhận, bộ đếm âm thanh, nhật ký Wine có giới
hạn và ảnh chụp. Trạng thái workflow thành công chỉ xác nhận bộ thử hoàn thành,
không có nghĩa mọi chức năng game đều đã hoạt động.
