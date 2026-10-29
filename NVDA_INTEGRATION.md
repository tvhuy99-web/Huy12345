# NVDA tự khởi động cùng môi trường — bản thử nghiệm

Bản này tích hợp NVDA 2026.3 vào APK. Mặc định, khi máy chủ lệnh của Wine đã sẵn sàng, Winlator chuẩn bị gói NVDA và khởi chạy NVDA. Không cần tự mở trình cài đặt Windows hay tải thêm tệp trên điện thoại.

## Sử dụng

1. Cài bản APK NVDA thử nghiệm trong [Releases](https://github.com/tvhuy99-web/Huy12345/releases). Android 8 trở lên, ARM64. Nếu báo khác chữ ký với bản đang dùng, giữ và sao lưu dữ liệu trước khi thay bản cài.
2. Để trống khoảng **400 MB** cho lần giải nén đầu, rồi khởi động môi trường. Những lần sau tái sử dụng gói đã giải nén.
3. Khi NVDA khởi tạo được, phần mở rộng đi kèm yêu cầu **chính NVDA** đọc câu “NVDA đã khởi động…”. Bản mới ưu tiên giọng tiếng Việt của bộ phát Android; eSpeak NG tiếng Việt là dự phòng khi giọng Android chưa sẵn sàng. Winlator chỉ báo sẵn sàng khi nhận được nhịp hoạt động do NVDA gửi, không dựa vào việc đã gửi lệnh mở tệp.
4. **Tự tắt TalkBack bằng thao tác quen thuộc của bạn.** Winlator không tắt TalkBack. Khi khám phá bằng chạm đã tắt, lớp cử chỉ Windows sẽ hoạt động nếu tùy chọn **Điều khiển Windows bằng cử chỉ** đang bật (mặc định bật). Bảng trợ năng đang mở sẽ đóng để trả vùng chạm cho môi trường.
5. Chạm ba hoặc bốn ngón, giữ ba ngón, hoặc nhấn nút Quay lại để mở menu giọng nói. Trong menu, vuốt để chọn và chạm hai lần để thực hiện; vuốt trái ba ngón để quay lại. Có các lệnh đọc, Start, màn hình nền, chuyển cửa sổ, chỉnh sửa, nhập chữ, khởi động lại NVDA và thoát môi trường. Thoát yêu cầu xác nhận vì sẽ đóng các ứng dụng Windows.
6. Giọng Android hiện được dùng cho lời đọc của NVDA qua cầu nối riêng; khi NVDA không phản hồi vẫn có đường phát thông báo điều khiển và menu cứu hộ; đây không phải TalkBack hay một dịch vụ đọc màn hình Android. Máy cần có bộ phát giọng tiếng Việt cho đường dự phòng này. Khi NVDA hoạt động bình thường, chính NVDA đọc menu và nội dung Windows.
7. Khi rời môi trường, hãy tự bật lại TalkBack để dùng giao diện Android. Tùy chọn cử chỉ có thể tắt/bật trong bảng **NVDA và trợ năng Windows** khi TalkBack đang bật. Cấu hình này không tự thay đổi TalkBack.

### Nhận nhiều ngón

Bản sửa ba/bốn ngón tham khảo luồng Android của GnollHack trong gói `GnollHack-BLIND-VI-PLAYER-TTS-FIX-20260831-R7.zip`: nhận từ Activity trước lớp con, tách ngón đang chạm và toàn bộ vệt chạm của phiên, tính độ đồng thuận hướng (0,72), và cho phép chạm nhiều ngón tối đa 520 ms. Các ngón có thể bắt đầu di chuyển trong lúc những ngón còn lại đang đặt xuống (cửa sổ nhập thêm ngón 300 ms). Chạm lặp dùng khoảng nghỉ 360 ms; bảng gán và quy tắc đã lưu giữ nguyên.

Chỉ phục hồi `ACTION_CANCEL` cho phiên ba/bốn ngón do cửa sổ Windows đang có tiêu điểm bắt từ đầu, các ID còn khớp và chưa ngón nào nhấc lên; phiên phải đủ điều kiện là chạm hoặc vuốt. Không phục hồi hủy một/hai ngón, mất tiêu điểm, tạm dừng, đổi chế độ, ID không khớp, chuyển động ngược hướng hoặc giữ quá lâu. Hủy thông thường ở lớp con cũng không được phục hồi. Thao tác đã phục hồi được kết thúc ngay để sự kiện nhấc tay đến sau không thực hiện lần hai.

Nếu hệ thống/OEM không chuyển sự kiện vào ứng dụng, việc xử lý hủy trong ứng dụng không thể khôi phục thao tác đó. Cần thử thực tế trên điện thoại; các kiểm thử MotionEvent không chứng minh rằng mọi ROM đều chuyển đủ sự kiện.

## Cử chỉ và tùy chỉnh theo môi trường

Trong danh sách môi trường, mở nút tùy chọn của môi trường → **Cử chỉ**. Chọn một cử chỉ, chọn chức năng trong danh sách hoặc bấm **Tùy chỉnh** để nhập tổ hợp như `Ctrl+C`, `Ctrl+Shift+S`, `Alt+F4`, `Windows+D`. Lưu áp dụng riêng cho môi trường đó. Nút **Mặc định** khôi phục phép gán ban đầu. Giao diện chỉ có danh sách, lựa chọn chức năng và nút thao tác; thông báo lỗi chỉ xuất hiện khi nhập tổ hợp không hợp lệ.

Có 40 cử chỉ có thể gán: bốn hướng và 12 đường vuốt hai chặng bằng một ngón; bốn hướng bằng hai, ba, bốn ngón; chạm một, hai, ba lần với mỗi số ngón từ một đến bốn. Các đường hai chặng gồm trái–phải, phải–trái, lên–xuống, xuống–lên và tám góc trái/phải–lên/xuống hoặc lên/xuống–trái/phải. Cử chỉ chưa có phép gán sẽ không gửi phím.

| Cử chỉ mặc định | Chức năng |
| --- | --- |
| Một ngón lên / xuống / trái / phải | Bốn phím mũi tên tương ứng |
| Một ngón chạm một lần / hai lần | Ngắt đọc / Enter |
| Hai ngón lên / xuống | Tab / Shift+Tab |
| Hai ngón trái / phải | Giữ chờ Ctrl / Windows |
| Hai ngón chạm một lần / hai lần | Đọc mục hiện tại / đọc cửa sổ hiện tại |
| Ba ngón chạm một lần / hai lần | Menu điều khiển / đọc lại câu gần nhất |
| Ba ngón trái / phải | Escape / phím cách |
| Ba ngón lên / xuống | Bảng F1–F12 / bảng số 0–9 |
| Bốn ngón lên / xuống | Windows+D / sao chép câu gần nhất |
| Bốn ngón trái / phải | Alt+Tab / Alt+Shift+Tab |
| Bốn ngón chạm một lần | Menu điều khiển |

Ctrl, Windows, Alt và Shift là các phím chờ một lần: bật bằng phép gán tương ứng, NVDA thông báo phím đang giữ; phím tiếp theo sẽ kết hợp rồi tự nhả. Lặp nhanh cùng cử chỉ trong 650 ms sẽ nhấn phím đó một lần; lặp sau khoảng đó hủy trạng thái chờ. Có thể giữ nhiều phím bổ trợ trước khi chọn phím chính. Trạng thái chờ được xóa khi rời môi trường hoặc hủy bảng chọn. Đây là trạng thái lô-gic trong ứng dụng, không giữ phím Windows ở trạng thái nhấn trong lúc người dùng đang lựa chọn.

Menu ba ngón gồm Điều hướng, Chỉnh sửa, Phím, Đọc màn hình, Cửa sổ, Công cụ, Thoát môi trường và Trở lại Windows. Trong menu/bảng phím: vuốt một ngón chọn mục, chạm hai lần một ngón để thực hiện, vuốt trái ba ngón quay lại. Chọn một phím F hoặc chữ số sẽ gửi phím rồi đóng bảng. Giữ ba ngón hoặc nút Quay lại vẫn mở menu cứu hộ ngay cả khi đã đổi phép gán chạm ba ngón.

Bàn phím chữ nằm trong nhóm **Phím**: vuốt trái/phải chọn ký tự, lên/xuống đổi nhóm, chạm hai lần nhập. Ba ngón phải nhập dấu cách; hai ngón lên/xuống gửi Tab/Shift+Tab; hai ngón phải xóa; ba ngón trái đóng. Khi đã giữ Ctrl/Alt/Shift/Windows, ký tự ASCII được chọn sẽ tạo tổ hợp phím; các ký tự tiếng Việt thông thường dùng đường nhập Unicode. Cần đặt tiêu điểm vào ô nhập trong Windows trước khi mở bàn phím.

**Đọc lại câu gần nhất** và **Sao chép câu gần nhất** sử dụng cùng lời đọc NVDA, tối đa 2048 ký tự. Lời thông báo điều khiển như “Đang giữ Ctrl” hay “Đã sao chép” không thay thế câu này. Sao chép đưa văn bản vào bộ nhớ tạm Android để dán vào ứng dụng khác. Câu gần nhất chỉ nằm trong bộ nhớ NVDA; riêng yêu cầu sao chép tạo phản hồi riêng tư tạm thời, được Android xóa ngay sau khi đọc và NVDA tự dọn sau ba giây nếu chưa được nhận. Không tạo nhật ký lời đọc trên điện thoại.

Các lệnh WFM/NVDA được hỗ trợ trực tiếp tiếp tục dùng cầu nối tương ứng. Những tổ hợp khác được gửi qua đường bàn phím X của Winlator và nhả phím theo thứ tự, không dựa vào `SendInput` của cầu nối cũ. Windows có ánh xạ phím và cờ bổ trợ riêng. Hủy/rời màn hình sẽ nhả các phím do cử chỉ đang gửi; phím người dùng đang giữ bằng bàn phím ngoài không bị nhả thay. Desktop/Start và các ứng dụng cụ thể vẫn phụ thuộc shell, Wine và khả năng xử lý phím của ứng dụng đó.

## Bản sửa màn hình Computer

Winlator mở WFM (trình quản lý tệp) ngay khi khởi động môi trường. Bản cũ thường chỉ đọc tiêu đề Computer vì WFM chưa đặt tiêu điểm vào danh sách, chưa có vòng Tab và chưa xử lý Enter mở mục. Danh sách WFM dùng LVS_OWNERDATA nên không được chứng minh bởi bài thử ListBox đơn giản trước đó.

Bản này biên dịch WFM từ nguồn cố định, áp dụng [bản sửa bàn phím](runtime-nvda/wfm/keyboard.patch), và cài vào `C:\winlator-nvda\filemanager\wfm.exe` trước khi mở môi trường. Giữ tệp WFM gốc và các tệp/cấu hình người dùng. WFM dùng libcdio đã có trong Wine; không tải DLL trên điện thoại.

Khi vào Computer, danh sách tự có tiêu điểm và chọn ổ đĩa đầu tiên. Lên/xuống đổi ổ hoặc tệp; Enter mở mục; Tab/Shift+Tab chuyển giữa danh sách, cây thư mục, địa chỉ và tìm kiếm. Backspace trong danh sách đi lên thư mục cha. Enter ở cây mở thư mục đã chọn, Enter ở địa chỉ đi tới đường dẫn đã nhập.

WFM xuất tên, loại và vị trí của mục **đang được chọn thực sự** qua các điều khiển văn bản Win32 ẩn có phiên bản. NVDA đọc các điều khiển này bằng lời gọi có thời hạn, không đoán tọa độ, không ghi danh sách vào tệp hay nhật ký. Đây là hỗ trợ riêng cho WFM; không khẳng định mọi danh sách tự vẽ của ứng dụng khác đã tương thích.

Để thử sau khi cập nhật APK, đóng rồi mở lại môi trường. Chờ NVDA, tự tắt TalkBack, thử vuốt xuống để nghe tên ổ đĩa khác rồi chạm hai lần mở ổ đó. Nếu chỉ có một ổ, thao tác xuống có thể vẫn ở cùng mục; thông báo có số thứ tự và tổng số mục để phân biệt.

## Sửa trường hợp luôn đọc ổ đĩa mục 1

Phản hồi trên điện thoại cho thấy cả vuốt lẫn nút mũi tên đều có thể đọc nguyên mục đầu tiên. Bản trước xác nhận NVDA nhận lệnh và đọc được lựa chọn, nhưng chưa chứng minh đường giả lập phím làm WFM đổi lựa chọn trên cấu hình Wine/Box64 đó.

Bản mới dùng giao thức lệnh WFM phiên bản 2. Với danh sách ổ/tệp, cây thư mục, Tab/Shift+Tab và Enter, NVDA gửi một mã thao tác cố định tới cửa sổ WFM. WFM xử lý trong chính luồng giao diện, thay đổi điều khiển thật và kiểm tra lại vị trí hoặc trạng thái. Các tham số chỉ là số, không có con trỏ hoặc lệnh thực thi tùy ý qua thông điệp riêng này. Nhập vào địa chỉ/tìm kiếm dùng thông điệp văn bản tiêu chuẩn của Windows.

Kết quả phân biệt đã đổi lựa chọn, đã xử lý và đã chạm đầu/cuối danh sách. Ở mục đầu, vuốt lên sẽ báo đã ở đầu; vuốt xuống phải đọc mục tiếp theo. Không coi việc đọc lại mục cũ là bằng chứng đã di chuyển thành công. Cả nút Android và cử chỉ dùng chung đường lệnh này.

Bài thử cố ý chặn `KeyboardInputGesture.send` và `SendInput` của đường cũ, xác nhận lệnh cũ thất bại, rồi yêu cầu WFM vẫn đổi ổ đĩa, mở thư mục, dùng Tab, phím cách và nhập đường dẫn. Bộ chặn chỉ cài trong môi trường kiểm thử, không được đóng gói vào APK. Đây là điều khiển trực tiếp riêng cho WFM; ứng dụng Windows khác vẫn phụ thuộc đường bàn phím và thông tin trợ năng của Wine.

Sau khi cập nhật APK, cần đóng và mở lại môi trường để nạp WFM mới. Không cần xóa môi trường hay dữ liệu.

## Lệnh và phản hồi

Android gửi lệnh được giới hạn tới phần mở rộng **trong NVDA**, nhận xác nhận theo mã lệnh và mã phiên ngẫu nhiên. Không chỉ gửi phím rồi báo thành công. Lệnh quá hạn, lệnh của phiên NVDA cũ và thao tác không hỗ trợ bị từ chối. Các lệnh chờ quá lâu bị bỏ để tránh thao tác muộn lên cửa sổ khác.

Các phím Windows thông thường được gửi bằng bộ gửi phím của NVDA, trước khi hỏi thông tin trợ năng, để truy vấn COM chậm không giữ lại phím. Lệnh riêng của NVDA như đọc cửa sổ và đọc liên tục được đưa vào bộ xử lý lệnh NVDA. Sau điều hướng, phần mở rộng đọc lại lựa chọn Win32 thật khi cần, hoặc yêu cầu NVDA đọc mục có tiêu điểm nếu thiếu lời đọc bình thường. Với ListBox, ComboBox và Button tiêu chuẩn, có đường đọc lựa chọn/trạng thái Win32 thật khi Wine thiếu sự kiện MSAA. Không suy đoán mục bằng ảnh, không ghi văn bản cửa sổ hoặc nội dung nhập vào tệp trả lời. Ô mật khẩu được che.

## Giọng đọc Android

NVDA vẫn lấy nội dung, xử lý điều hướng và quyết định lời cần đọc. Bộ phát `winlatorAndroid` chuyển lời đọc cùng dấu mốc sang `TextToSpeech` của Android; không cần bật TalkBack, không cài bộ giọng Windows vào Wine. Không đóng gói giọng Google/Samsung trong APK: sử dụng bộ phát mặc định và dữ liệu giọng tiếng Việt đã có trên điện thoại.

Mặc định ưu tiên giọng tiếng Việt đã cài không cần mạng. Nếu từng chọn một giọng trong ứng dụng, lựa chọn đó được giữ lại. Giọng cần mạng được ghi rõ trong danh sách. Khi chưa có giọng tiếng Việt sẵn sàng, NVDA giữ eSpeak dự phòng và bảng điều khiển báo thiếu dữ liệu.

Mở **NVDA và trợ năng Windows** rồi chọn **Nghe thử giọng Android qua NVDA**, **Chọn giọng tiếng Việt Android**, hoặc **Mở cài đặt giọng đọc Android**. Nếu phải cài thêm dữ liệu tiếng Việt trong cài đặt hệ thống, đóng và mở lại môi trường sau khi cài xong.

Cầu nối TCP chỉ nghe tại `127.0.0.1`, cổng ngẫu nhiên, xác thực bằng mã 32 byte riêng cho phiên ứng dụng. Tệp cấu hình chỉ chứa địa chỉ và mã xác thực, không chứa văn bản được đọc. Văn bản chỉ đi qua bộ nhớ và bộ phát đã chọn; giọng cần mạng có thể sử dụng dịch vụ của bộ phát theo cấu hình đó. Không ghi lời đọc vào tệp/journal của cầu nối.

NVDA ngắt lời đọc cũ bằng số thế hệ mới; callback cũ không được tính là đã đọc mục mới. Dấu mốc và sự kiện đọc xong chỉ gửi về sau callback của bộ phát. Khi tạm dừng, cầu nối dùng vị trí từ nếu bộ phát cung cấp; bộ phát không cung cấp vị trí có thể đọc lại đầu đoạn hiện tại khi tiếp tục. Âm thanh dừng khi rời màn hình môi trường. Mất kết nối thì bỏ lời cũ và thử nối lại, không đọc lại dữ liệu tồn đọng.

Kiểm thử Wine dùng **NVDA thật và driver mới**, với một đầu nhận mô phỏng Android để kiểm tra xác thực, tiếng Việt, dấu mốc hoàn tất và ngắt đọc. Kiểm thử Android kiểm tra hàng đợi, phân đoạn Unicode, callback muộn và khung giao thức. Các kiểm thử này không chứng minh chất giọng Google/Samsung trên điện thoại; vẫn cần nghe thử trên thiết bị thật.

## Trình đơn NVDA và chuyển cửa sổ

Thông báo “không xác định, đang có focus, ẩn” khi duyệt trình đơn là lỗi thiếu thông tin trợ năng của Wine. Bản sửa mở trình đơn cảm ứng dựa trên chính danh sách mục, trạng thái và bộ xử lý lệnh của NVDA đang chạy. Không dùng một danh sách lệnh NVDA sao chép cố định. Vuốt lên/xuống để chọn, chạm hai lần để vào mục hoặc trình đơn con, vuốt trái hai ngón để quay lại hoặc đóng. Mục không khả dụng được thông báo rõ.

Đường điều khiển hộp thoại NVDA dùng điều khiển wx thật: Tab/Shift+Tab đổi tiêu điểm; danh sách và hộp chọn đọc mục hiện tại; nút, hộp đánh dấu và thanh trượt có các thao tác trực tiếp. Nhãn cài đặt lấy từ nhãn đi kèm trong bố cục wx, ví dụ “Tốc độ”, “Cao độ”, thay vì chỉ đọc một con số. Đây là đường riêng cho cửa sổ NVDA, không có nghĩa tất cả điều khiển của ứng dụng Windows khác đều đã được hỗ trợ.

Chạm ba ngón mở menu điều khiển. Nhóm **Đọc màn hình** có **Mở trình đơn NVDA**; nhóm **Cửa sổ** có **Danh sách cửa sổ đang mở** và **Quay về trình quản lý tệp**. Trong danh sách cửa sổ, vuốt chọn rồi chạm hai lần. Danh sách lấy tiêu đề cửa sổ thật, khôi phục cửa sổ đang thu nhỏ khi cần và kiểm tra lại cửa sổ tiền cảnh. Vuốt trái bốn ngón gửi Alt+Tab để chuyển cửa sổ; hoặc mở danh sách cửa sổ trong menu. Có thể đóng trình đơn rồi trở về cửa sổ trước đó.

Computer là trang đầu của trình quản lý tệp WFM. Ổ C là mục được chọn đầu tiên, không phải toàn bộ môi trường Windows. Trong ổ hoặc thư mục, mở nhóm **Chỉnh sửa** rồi chọn **Backspace** để lên thư mục cha; từ gốc ổ đĩa sẽ về Computer. Không có thư mục cha phía trên Computer. Muốn dùng ứng dụng khác, chuyển cửa sổ; muốn trở về Android, dùng **Thoát môi trường Windows**, xác nhận rồi tự bật lại TalkBack. Thoát môi trường đóng các ứng dụng Windows đang chạy.

Màn hình nền và Start phụ thuộc shell của Wine. Nếu không tìm được màn hình nền điều khiển được hoặc nút Start thật, NVDA thông báo phần đó chưa có; không coi việc gửi phím rồi đọc lại ổ C là đã mở thành công. Nhánh mở Start khi shell có nút Start thật vẫn cần kiểm tra trên cấu hình Winlator của điện thoại.

## Mô phỏng mở rộng

[runtime-nvda/test_runtime_audit.py](runtime-nvda/test_runtime_audit.py) chạy cùng NVDA thật, WFM thật và các cửa sổ Win32 kiểm thử trong Wine. Bài thử ghi `runtime-audit.json` vào artifact chẩn đoán của GitHub Actions. Kết quả tách rõ **pass**, **limited**, **fail**; trường hợp chỉ xác nhận thông báo thiếu shell không được tính là đã truy cập được màn hình nền hoặc Start.

Các phép thử đối chiếu lời đọc trong nhật ký NVDA với điều khiển hoặc cửa sổ thật. Trình đơn NVDA được duyệt nhãn các cấp; Cấu hình được mở bằng chính mục trình đơn. Các nhóm cài đặt được khảo sát qua vòng Tab, không tự thay đổi cài đặt. Chuyển cửa sổ, WFM và điều khiển NVDA còn được thử khi cố ý chặn hai đường giả lập phím cũ. Cửa sổ kiểm thử Win32 có danh sách, nút, hộp đánh dấu, ô nhập tiếng Việt, mật khẩu, hộp chọn, nút chọn, thanh trượt, hộp thoại xác nhận, chọn tệp và trình đơn bật lên. Đây là đại diện các điều khiển, không phải kiểm thử tất cả trình cài đặt hoặc trò chơi.

Mô phỏng Linux/Wine không chạy Android/Box64 trên điện thoại. Chất giọng Android, cử chỉ phần cứng, shell cụ thể của Winlator và ứng dụng Windows người dùng cài vẫn cần thử trên thiết bị. Bộ kiểm tra không được đóng gói vào APK; các dữ liệu và nhật ký trong CI chỉ là dữ liệu thử nghiệm.

## Cách tích hợp và giới hạn

- Gói gốc lấy từ NV Access, phiên bản cố định 2026.3, SHA-256 `a8a87cb823da0c62cfbae4a444ae5ae238d54dc82ad6d46d3fdb3fef082799b2`. Không dùng tệp tải về khi mã kiểm tra không khớp.
- Gói portable dùng `nvda_noUIAccess.exe` làm `nvda.exe`, tương ứng cách tạo portable của NVDA. Giữ các thành phần tiếng Việt, giọng eSpeak, thư viện và giấy phép trong gói.
- Bộ khởi chạy cung cấp các đầu vào/đầu ra Windows hợp lệ cho Python nhúng. Lỗi tiến trình NVDA không được coi là đã khởi tạo thành công.
- Wine 10.10 thiếu một số hàm mà NVDA 2026.3 nạp ngay lúc nhập mô-đun các mô-đun `winBindings`. Bản tương thích chỉ trì hoãn lỗi đối với **hàm chưa tồn tại** đến lúc thật sự gọi nó; khi đó vẫn báo `WinError 120` hoặc `E_NOTIMPL` (không hỗ trợ). Hàm có sẵn giữ nguyên cách gọi. Không tạo thông tin MSAA/UIA giả, không mô phỏng kết quả thành công cho hàm thiếu.
- Mã mô-đun NVDA đã sửa nằm trong `source/winBindings/` và `source/watchdog.py` của gói portable. Giấy phép gốc nằm trong `documentation/copying.txt` và tệp `NVDA-COPYING.txt` đi kèm APK. [Mã gốc cố định](https://github.com/nvaccess/nvda/tree/7eb1738dd1556775145453fdd8b6b7ca6b397693), [cách tạo bản tương thích](runtime-nvda/compat.py), [mã phần tích hợp](runtime-nvda/).
- Nếu Wine báo không hỗ trợ hủy lời gọi COM, NVDA bỏ qua bước bật cơ chế đó; khả năng phục hồi khi ứng dụng làm treo lời gọi COM sẽ bị hạn chế. Nút Dừng vẫn có đường kết thúc đúng tiến trình NVDA do bộ khởi chạy tạo ra.
- Cấu hình người dùng nằm riêng trong `C:\winlator-nvda\config`; cập nhật bộ chương trình không ghi đè cấu hình này. Gói chương trình được kiểm tra SHA-256 và giải nén vào thư mục tạm trước khi đưa vào sử dụng.
- Phần mở rộng ghi trạng thái sẵn sàng, mã tiến trình và thời gian hoạt động; không ghi nhật ký lời đọc. Ngoại lệ có chủ đích là phản hồi tạm thời khi người dùng yêu cầu sao chép câu gần nhất, được xóa sau khi nhận hoặc sau ba giây. Khi chạy trên điện thoại, NVDA được gọi với `--no-logging`.
- NVDA phát tiếng không đồng nghĩa đọc đầy đủ mọi ứng dụng. Thông tin trợ năng và sự kiện tiêu điểm vẫn phụ thuộc Wine và từng phần mềm. Người dùng đã xác nhận bản trước đọc được khi yêu cầu đọc cửa sổ, nhưng điều hướng còn im lặng. Chế độ cử chỉ và đường phản hồi mới vẫn cần thử trên điện thoại Wine/Box64; kết quả máy Linux không thay thế bước đó.

## Kiểm tra trước khi phát hành

Workflow dựng APK phải kiểm tra gói, chạy cửa sổ Windows thật của cầu nối cũ, chạy **NVDA thật** trong Wine, nhận trạng thái từ NVDA và thu được tín hiệu âm thanh ở đầu ra thử nghiệm. Bài thử còn yêu cầu lệnh Down đổi lựa chọn ListBox thật và NVDA đọc Beta, Tab/Shift+Tab đổi tiêu điểm, Enter kích hoạt, Space đổi trạng thái, nhập được tiếng Việt và không lộ mật khẩu. Bài thử mới còn chạy chính WFM: Computer phải đọc ổ đĩa, đổi lựa chọn và mở bằng Enter; thư mục kiểm thử phải đọc Alpha/Beta, mở tệp bên trong, đi lên thư mục cha, đổi vùng bằng Tab/Shift+Tab và đi tới địa chỉ được nhập. Sau đó mới chạy kiểm thử Android, xác minh gói NVDA trong APK và kiểm tra chữ ký. Kiểm tra tương thích Wine/NVDA và dựng APK hiện dùng chung `.github/workflows/accessibility-apk.yml`; quy trình dò riêng đã được bỏ để tránh chạy trùng. Bước `probe.py --require-ready` phải xác nhận khởi tạo, âm thanh và các kiểm tra bắt buộc trước khi dựng APK.

Nhật ký và âm thanh của bài thử chỉ dùng dữ liệu thử nghiệm. Người dùng không cần gửi mật khẩu hoặc nhật ký có nội dung riêng tư để báo lỗi; có thể báo câu trạng thái trong bảng NVDA và ứng dụng Windows đang mở.

Kiểm tra cử chỉ mới còn bao gồm các đường vuốt hai chặng, chạm hai/ba lần nhiều ngón, phím bổ trợ chờ một lần, nhấn đơn bằng hai lần vuốt, nhả phím khi hủy, hồ sơ riêng từng môi trường và giao diện nhập tổ hợp. Kiểm thử Wine dùng sự kiện phím X thật để kiểm tra Tab, mũi tên, F12, Ctrl+C và giữ nguyên lịch sử lời đọc qua thông báo điều khiển. Điều này không thay thế thử cử chỉ phần cứng trên điện thoại.
