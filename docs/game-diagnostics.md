# Chẩn đoán game — APK 49

Đây là bản thử để phân biệt lỗi mở cửa sổ, nơi nhận bàn phím và đường đọc của
game. Chưa khẳng định Zetianji đã hoạt động đầy đủ trên Android/Box64.

## Cách thử trên điện thoại

1. Đóng môi trường Windows cũ, cài cập nhật APK 49 rồi mở lại môi trường.
2. Mở `zetianji.exe` từ trình quản lý tệp một lần. Nếu cửa sổ không hiện, mở
   **Chẩn đoán game → Hiện cửa sổ ứng dụng vừa mở**.
3. Thử mũi tên và Enter. Nếu đã vào đúng cửa sổ, đóng game bằng Alt+F4 và xử lý
   hộp xác nhận nếu có. Công cụ không buộc kết thúc tiến trình.
4. Chọn **Bật nhật ký giọng game**, rồi mở lại game từ trình quản lý tệp.
   Việc mở lại giúp ghi được từ bước khởi tạo bộ giọng.
5. Thử vài thao tác, rồi chọn **Chia sẻ nhật ký công cụ** và gửi tệp nhật ký.

Có thể vào Chẩn đoán game từ bảng NVDA, hoặc khi TalkBack đã tắt: nhấn Quay lại
để mở **Menu điều khiển → Công cụ → Chẩn đoán game**. Ba thao tác cũng có trong
**Thao tác cử chỉ** để bấm thủ công. Người dùng tự bật/tắt TalkBack.

## Khôi phục

Đóng game, rồi chọn **Khôi phục bộ giọng game**. Công cụ kiểm tra mã SHA-256
của bản sao gốc trước khi đưa lại `xinyitts.dll`. Nếu tệp hiện tại hoặc bản sao
lưu đã bị thay đổi, công cụ từ chối ghi đè và ghi lý do vào nhật ký.

Nếu vừa khởi động lại NVDA hoặc môi trường, hãy mở game một lần rồi đóng game
để công cụ nhận lại đúng đường dẫn. Không cần xóa dữ liệu Winlator.

## Phạm vi bản thử

- Hiện cửa sổ chỉ xét ứng dụng vừa mở và các tiến trình con được theo dõi, có
  kiểm tra thời gian tạo tiến trình để loại PID đã được dùng lại. Cửa sổ phải
  có kích thước và thành phần điều khiển phù hợp; không tự hiện mọi cửa sổ ẩn.
- Trạng thái cửa sổ của Windows và tiêu điểm bàn phím X được kiểm tra riêng.
  Android đối chiếu XID với HWND của cửa sổ còn hiển thị và có bộ nhận phím.
  Gửi được sự kiện bàn phím vẫn chưa chứng minh game đã xử lý sự kiện đó.
- Bộ ghi giọng chỉ nhận bản `xinyitts.dll` x86 đã kiểm tra, SHA-256
  `54ce75b5c6441d739ad08a99876cea5bc52b3a91b7498ba21bc7b3f26b3265e3`.
  Bản khác sẽ bị từ chối. Không thay đổi cấu hình giọng hay thêm thư viện
  của game vào APK.
- Bộ ghi giữ nguyên thư viện gốc dưới tên `winlator-voice-original.dll`;
  theo dõi các hàm InitA/W, SpeakA/W, Speak2A/W, Stop, Pause, SetNotify và
  Uninit. Các export còn lại chuyển tiếp nguyên đến thư viện gốc, giữ tên
  và ordinal. Không chèn mã vào tiến trình đang chạy.
- Mỗi lời gọi có PID, luồng, số thứ tự, thời điểm bắt đầu/kết thúc, kết quả,
  thời gian chạy, mã ký tự và độ dài chuỗi giới hạn. Không ghi nội dung chuỗi
  lấy từ DLL. `lastError` có thể là giá trị còn lại từ lời gọi trước; không
  tự suy ra lỗi chỉ từ trường này.
  Giá trị trả về thô của SetNotify/Uninit không có hợp đồng thành công/thất bại
  được xác nhận; không coi giá trị 0 của các hàm này là bằng chứng lỗi.
- Nhật ký DLL được nhập vào nhật ký công cụ. Câu NVDA nhận và các sự kiện
  phát giọng Android vẫn được ghi qua các kênh riêng. Giới hạn xuất nhật ký
  là 500.000 ký tự; bản cũ tự được loại. Bộ ghi nội bộ quay vòng và báo mất
  đoạn nếu dữ liệu đến quá nhanh, nên không coi thiếu một đoạn là bằng chứng
  game chưa gọi hàm.

Kiểm thử Wine và Robolectric giúp phát hiện lỗi trước khi đóng gói, nhưng
không thay thế thử nghiệm trên OnePlus của người dùng.

## Bằng chứng của bản này

- [Đóng gói APK 49](https://github.com/tvhuy99-web/Huy12345/actions/runs/41018169567):
  124 kiểm thử Android qua; 28 kiểm thử logic chẩn đoán và 5 kiểm thử cấu hình
  bộ ghi qua. Kiểm thử PE32 và cửa sổ ẩn nhận phím Down/Enter qua. Kiểm thử
  hồi quy NVDA: 54 tình huống đạt, 4 có giới hạn, 1 kiểm tra tùy chọn về tên
  mục popup Wine vẫn chưa đạt như bản 48; các kiểm tra bắt buộc đều qua.
- [Thử với đúng game Zetianji](https://github.com/tvhuy99-web/Huy12345/actions/runs/41018615597):
  kiểm tra lại SHA-256 của archive, chạy với cùng mã bộ ghi và addon như APK.
  Trong 60 giây, PID game có InitA bắt đầu/kết thúc (trả 1) và SetNotify bắt
  đầu/kết thúc; không ghi nhận lời gọi Speak. Tiến trình thử riêng sau đó gọi
  SpeakW và SpeakA thành công; NVDA nhận đúng hai câu kiểm tra và có âm thanh.
  Không trộn câu thử của tiến trình kiểm tra vào kết quả lời đọc của game.

Kết quả hiện khoanh vùng đến đường gọi nội dung từ game. Chưa chứng minh được
nguyên nhân cụ thể là cấu hình, trạng thái game hay cơ chế thông báo của bộ
giọng; cần đối chiếu nhật ký điện thoại trước khi thay đổi những phần đó.
