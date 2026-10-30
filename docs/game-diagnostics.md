# Chẩn đoán game — APK 51

Đây là bản thử để phân biệt lỗi mở cửa sổ, nơi nhận bàn phím và đường đọc của
game. Chưa khẳng định Zetianji đã hoạt động đầy đủ trên Android/Box64.

## Cách thử trên điện thoại

1. Đóng môi trường Windows cũ, cài cập nhật APK 51 rồi mở lại môi trường.
2. Trong trình quản lý tệp, chọn `zetianji.exe` nhưng chưa mở game.
3. Chọn **Chẩn đoán game → Chuẩn bị nhật ký cho game đã chọn**. Chờ công cụ báo
   đã chuẩn bị, rồi mới nhấn Enter để mở game. Không cần mở game một lần trước.
4. Nếu cửa sổ không hiện, thử **Hiện cửa sổ ứng dụng vừa mở** hoặc **Kiểm tra
   ứng dụng vừa mở**. Chờ ít nhất 50 giây để thu cả hai mốc kiểm tra sâu.
5. Chọn **Chia sẻ nhật ký công cụ** và gửi tệp nhật ký. Nếu phát hiện game còn
   chạy khi chuẩn bị, thoát môi trường rồi làm lại từ bước chọn tệp, tránh
   phải tìm cách đóng cửa sổ đang ẩn.

Có thể vào Chẩn đoán game từ bảng NVDA, hoặc khi TalkBack đã tắt: nhấn Quay lại
để mở **Menu điều khiển → Công cụ → Chẩn đoán game**. Các thao tác cũng có trong
**Thao tác cử chỉ** để bấm thủ công. Người dùng tự bật/tắt TalkBack.

## Khôi phục

Đóng game, rồi chọn **Khôi phục bộ giọng game**. Công cụ kiểm tra mã SHA-256
của bản sao gốc trước khi đưa lại `xinyitts.dll`. Nếu tệp hiện tại hoặc bản sao
lưu đã bị thay đổi, công cụ từ chối ghi đè và ghi lý do vào nhật ký.

Có thể chọn lại tệp exe trong trình quản lý tệp để khôi phục mà không cần
mở game. Không cần xóa dữ liệu Winlator.

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

## Nội dung bổ sung trong bản 50

- WFM công bố đường dẫn chính xác của một tệp đang chọn qua caption lưu sẵn;
  chuẩn bị/khôi phục bộ ghi không cần khởi chạy game để đoán đường dẫn.
- Trước/sau khi chuẩn bị: SHA-256 và kích thước DLL/bản sao, các bước sao lưu,
  ghi manifest, cài bộ ghi, khôi phục và mã lỗi tại đúng bước. Bản ghi DLL 49
  có thể được cập nhật, giữ nguyên DLL gốc đã xác minh.
- Nạp DLL gốc có dấu bắt đầu/kết thúc riêng, mã lỗi và thời gian. Các lời gọi
  có giờ UTC mili giây để đối chiếu với NVDA và bộ phát Android. Giá trị trả
  về của SetNotify/Uninit được đánh dấu không có hợp đồng kết quả xác nhận.
- Tùy chọn `tts.ini/type`, `usrvoice.ini/engine`, `numericMode` và cờ đầu của
  `yuyn.ini` được lấy theo danh sách cho phép. Không xuất toàn bộ INI.
- Sau 0,7 / 5 / 15 giây có bộ quan sát 32 bit độc lập: PID/thời gian tạo, CPU,
  DLL đã nạp (tối đa 96), luồng (tối đa 32), cửa sổ (tối đa 8), kiểu/style,
  hiển thị và phép thử WM_NULL tối đa 200 ms mỗi cửa sổ. Tên DLL dài được cắt
  và đánh dấu. Lỗi truy vấn được ghi, không tự suy ra DLL bị thiếu chỉ từ
  một truy vấn thất bại.
- Yêu cầu ShowWindowAsync có ID, HWND/PID/luồng, kiểu hiển thị, kết quả bắt
  đầu yêu cầu và lastError. Kết quả cửa sổ thật được ghi sau đó. Bộ quan sát
  không dùng chung luồng giao diện NVDA; quá 8 giây chỉ dừng helper của công
  cụ. Không dừng game, không đọc bộ nhớ tùy ý hoặc chèn mã vào game.
- WM_NULL được trả lời chỉ chứng minh cửa sổ xử lý được thông điệp thử đó.
  Không trả lời có thể do giao diện đang bận hoặc hạn chế Wine; chưa đủ để
  kết luận game đã treo hoặc đang chờ chính xác một DLL nào.

Các kết quả mô phỏng bản 49 vẫn có thể xem ở
[lượt đóng gói 49](https://github.com/tvhuy99-web/Huy12345/actions/runs/41018169567)
và [lượt thử đúng game](https://github.com/tvhuy99-web/Huy12345/actions/runs/41018615597).
Bản đó ghi nhận InitA và SetNotify nhưng chưa ghi nhận Speak trong 60 giây;
không suy rộng kết quả Wine trên máy tính thành nguyên nhân trên điện thoại.

## Kiểm chứng bản 50

- [Đóng gói và kiểm thử APK 50, lượt 2](https://github.com/tvhuy99-web/Huy12345/actions/runs/41032963187/attempts/2):
  124 kiểm thử Android qua; 31 kiểm thử logic chẩn đoán và 7 kiểm thử bộ ghi qua.
  Kiểm thử PE32 giữ nguyên ABI/kết quả/lastError, khôi phục DLL từng byte,
  phân biệt cửa sổ ẩn còn phản hồi với cửa sổ ngừng xử lý thông điệp, chuẩn bị
  từ tệp WFM đang chọn trước khi mở chương trình và ghi kết quả kiểm tra thủ
  công đều qua. Kiểm thử hồi quy: 54 đạt, 4 có giới hạn, 1 kiểm tra tùy chọn
  về tên mục popup Wine chưa đạt; các kiểm tra bắt buộc qua.
- Lượt chạy đầu của cùng mã gặp lỗi bộ nhớ trong chương trình thử hộp xác
  nhận của Wine. Chạy lại cùng mã vượt qua; chưa kết luận đã khắc phục nguyên
  nhân của lần lỗi Wine đó. Không bỏ qua kiểm thử xác nhận/hủy để đóng gói.
- [Thử với đúng game](https://github.com/tvhuy99-web/Huy12345/actions/runs/41034287435):
  bộ ghi mới bắt được nạp DLL gốc và InitA thành công. Game chưa gọi Speak
  trong 60 giây; tiến trình đối chứng riêng gọi SpeakA/W và NVDA đọc được.
  Đây là kết quả Wine trên Linux, cần nhật ký mới trên điện thoại để đối chiếu.
- APK dùng cùng chứng chỉ bản 49; SHA-256:
  `3a2d3c35141508c587dd8baac724b31d97a3c2176efe243418b2bc4f8829f35a`.


## Điều tra từ nhật ký điện thoại bản 50

Nhật ký (7) xác nhận đã cài bộ ghi trước khi mở game: 17:09:59 và 17:10:12
ngày 30/10/2026, giờ Việt Nam. Game còn chạy sau hơn hai phút, cửa sổ WTWindow
ẩn; các phép WM_NULL ở mốc 5/15 giây báo 1460. Snapshot module có resource.irf,
aisound.dll, RICHED20.DLL nhưng chưa có xinyitts.dll/usrvoice.dll; chưa có bản ghi
proxy.loadOriginal hoặc xytts*. Không suy ra từ đó rằng một DLL cụ thể gây lỗi,
hoặc rằng game chưa từng thử nạp DLL giữa các mốc kiểm tra. Người dùng đã thực
hiện đúng bước chuẩn bị; không yêu cầu lặp lại cùng một thử nghiệm bản 50.

## Nội dung bổ sung trong bản 51

- Bộ quan sát nhận cả thời gian tạo dự kiến và kiểm tra ngay trong helper, trước
  khi xét module/luồng/debugger. PID tái sử dụng hoặc tiến trình đã thoát bị từ chối.
- Tại 15/45 giây và khi chọn Kiểm tra ứng dụng vừa mở, nếu có cửa sổ ẩn không
  trả lời phép thử, có thể gắn debugger PE32 trong thời gian ngắn. Mốc 0,7/5 giây
  và thao tác hiện cửa sổ vẫn là kiểm tra cơ bản. Không gắn nếu có debugger khác.
- DebugActiveProcess tạm dừng các luồng. Helper chụp tại CREATE_PROCESS_DEBUG_EVENT,
  trước khi tiếp tục đến breakpoint tổng hợp do thao tác gắn debugger tạo ra;
  không nhầm breakpoint đó với nơi game vốn đang chờ. GetThreadContext dùng
  CONTEXT_CONTROL, không đổi thanh ghi và không dùng SuspendThread để giữ riêng
  một luồng. Sau đó tiếp tục các sự kiện và gọi DebugActiveProcessStop.
- DebugSetProcessKillOnExit(FALSE) được thiết lập thông qua tiến trình con dùng
  một lần của chính helper, trước khi gắn vào game. Cấu hình áp dụng cho các kết
  nối debugger về sau trên cùng luồng. Nếu thiết lập hoặc nhả tiến trình con không
  thành công, không gắn debugger vào game. Chỉ tiến trình con của helper được dừng. Hết 8 giây, NVDA chỉ
  dừng helper. Kiểm thử Wine bắt buộc kết thúc helper trong lúc game đang bị giữ
  bởi sự kiện debugger, rồi xác nhận game vẫn sống và luồng heartbeat chạy tiếp.
- Tối đa 12 luồng, mỗi luồng: vị trí lệnh, tối đa 8 địa chỉ frame pointer chưa xác
  minh và 16 địa chỉ ứng viên nằm trong vùng mã của module. Chỉ đọc 512 byte stack
  mỗi luồng; không xuất các byte stack, tham số hàm, chuỗi hoặc nội dung game.
  Chuỗi frame pointer có thể thiếu/sai trên mã bỏ frame pointer; ứng viên trên
  stack không phải call stack đã unwind. Không kết luận một hàm gây lỗi từ một
  địa chỉ hoặc export gần đó. Tên export gần nhất kèm khoảng cách tối đa 4096 byte
  là gợi ý, không phải ký hiệu đã xác nhận tại vị trí lệnh.
- Module + RVA cho phép đối chiếu các lần chụp. Nhiều mốc giống nhau chỉ thu hẹp
  hướng điều tra, chưa chứng minh deadlock. Lỗi API/bitness/đọc bộ nhớ được ghi
  riêng. Wine trên Linux qua kiểm thử không bảo đảm Wine/Box64 trên điện thoại
  hỗ trợ cùng hành vi; nhật ký mới cần xác nhận attached/detached/contextOk.
- Bản ghi game.probe.debugger tách trạng thái gắn/nhả khỏi game.probe.thread;
  giữ ID/PID/TID để đối chiếu với cửa sổ, khởi động game và bộ giọng.

Tham khảo hợp đồng API: [DebugActiveProcess](https://learn.microsoft.com/en-us/windows/win32/api/debugapi/nf-debugapi-debugactiveprocess),
[Debugging events](https://learn.microsoft.com/en-us/windows/win32/debug/debugging-events),
[DebugSetProcessKillOnExit](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-debugsetprocesskillonexit),
[DebugActiveProcessStop](https://learn.microsoft.com/en-us/windows/win32/api/debugapi/nf-debugapi-debugactiveprocessstop).
