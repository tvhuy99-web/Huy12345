# NVDA tự khởi động cùng môi trường — bản thử nghiệm

Bản này tích hợp NVDA 2026.3 vào APK. Mặc định, khi máy chủ lệnh của Wine đã sẵn sàng, Winlator chuẩn bị gói NVDA và khởi chạy NVDA. Không cần tự mở trình cài đặt Windows hay tải thêm tệp trên điện thoại.

## Sử dụng

1. Cài bản APK NVDA thử nghiệm trong [Releases](https://github.com/tvhuy99-web/Huy12345/releases). Android 8 trở lên, ARM64. Nếu báo khác chữ ký với bản đang dùng, giữ và sao lưu dữ liệu trước khi thay bản cài.
2. Để trống khoảng **400 MB** cho lần giải nén đầu, rồi khởi động môi trường. Những lần sau tái sử dụng gói đã giải nén.
3. Khi NVDA khởi tạo được, phần mở rộng đi kèm yêu cầu **chính NVDA** đọc câu “NVDA đã khởi động…”. Bản mới ưu tiên giọng tiếng Việt của bộ phát Android; eSpeak NG tiếng Việt là dự phòng khi giọng Android chưa sẵn sàng. Winlator chỉ báo sẵn sàng khi nhận được nhịp hoạt động do NVDA gửi, không dựa vào việc đã gửi lệnh mở tệp.
4. **Tự tắt TalkBack bằng thao tác quen thuộc của bạn.** Winlator không tắt TalkBack. Khi khám phá bằng chạm đã tắt, lớp cử chỉ Windows sẽ hoạt động nếu tùy chọn **Điều khiển Windows bằng cử chỉ** đang bật (mặc định bật). Bảng trợ năng đang mở sẽ đóng để trả vùng chạm cho môi trường.
5. Chạm ba hoặc bốn ngón, giữ ba ngón, hoặc nhấn nút Quay lại để mở menu giọng nói. Trong menu, vuốt để chọn và chạm hai lần để thực hiện; vuốt trái hai ngón để đóng. Có các lệnh đọc, Start, màn hình nền, chuyển cửa sổ, chỉnh sửa, nhập chữ, khởi động lại NVDA và thoát môi trường. Thoát yêu cầu xác nhận vì sẽ đóng các ứng dụng Windows.
6. Giọng Android hiện được dùng cho lời đọc của NVDA qua cầu nối riêng; khi NVDA không phản hồi vẫn có đường phát thông báo điều khiển và menu cứu hộ; đây không phải TalkBack hay một dịch vụ đọc màn hình Android. Máy cần có bộ phát giọng tiếng Việt cho đường dự phòng này. Khi NVDA hoạt động bình thường, chính NVDA đọc menu và nội dung Windows.
7. Khi rời môi trường, hãy tự bật lại TalkBack để dùng giao diện Android. Tùy chọn cử chỉ có thể tắt/bật trong bảng **NVDA và trợ năng Windows** khi TalkBack đang bật. Cấu hình này không tự thay đổi TalkBack.

## Cử chỉ khi TalkBack đã tắt

| Cử chỉ | Lệnh Windows / NVDA |
| --- | --- |
| Vuốt một ngón lên / xuống | Mũi tên lên / xuống |
| Vuốt một ngón trái / phải | Shift+Tab / Tab |
| Chạm hai lần một ngón | Enter |
| Chạm một lần một ngón | Ngắt lời đọc |
| Chạm một lần hai ngón | Đọc mục đang có tiêu điểm |
| Chạm hai lần hai ngón | Phím cách |
| Vuốt hai ngón lên / xuống | Đọc cửa sổ / đọc liên tục |
| Vuốt hai ngón trái / phải | Escape / Alt+Tab |
| Chạm ba hoặc bốn ngón; giữ ba ngón | Menu điều khiển bằng giọng nói |
| Vuốt ba ngón lên / xuống / trái | Home / End / Backspace |
| Vuốt ba ngón phải | Bàn phím chọn ký tự bằng giọng nói |

Mũi tên chỉ di chuyển trong điều khiển đang được chọn; dùng Tab/Shift+Tab để chuyển giữa các điều khiển. Cử chỉ không bấm chuột vào vị trí chạm, không cần tìm tọa độ của nút. Chuột và bàn phím ngoài vẫn dùng đường nhập hiện có.

Bàn phím giọng nói: vuốt trái/phải để chọn ký tự, lên/xuống để đổi nhóm chữ thường, chữ hoa, số, chữ Việt và dấu; chạm hai lần để nhập. Chạm hai ngón nhập dấu cách, vuốt phải hai ngón xóa, chạm hai lần hai ngón gửi Enter, vuốt trái hai ngón đóng bàn phím. Đây là cách nhập từng ký tự ban đầu, còn chậm; bộ chữ Việt ban đầu có chữ thường có dấu. Cần đưa tiêu điểm vào ô nhập trong Windows trước khi mở bàn phím.

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

Chạm ba ngón mở menu điều khiển rồi chọn **Mở trình đơn NVDA**, **Danh sách cửa sổ đang mở** hoặc **Quay về trình quản lý tệp**. Trong danh sách cửa sổ, vuốt chọn rồi chạm hai lần. Danh sách lấy tiêu đề cửa sổ thật, khôi phục cửa sổ đang thu nhỏ khi cần và kiểm tra lại cửa sổ tiền cảnh. Vuốt phải hai ngón chuyển nhanh sang một cửa sổ khác, không còn phụ thuộc phím Alt+Tab giả lập. Có thể đóng trình đơn rồi trở về cửa sổ trước đó.

Computer là trang đầu của trình quản lý tệp WFM. Ổ C là mục được chọn đầu tiên, không phải toàn bộ môi trường Windows. Trong ổ hoặc thư mục, vuốt trái ba ngón (Backspace) để lên thư mục cha; từ gốc ổ đĩa sẽ về Computer. Không có thư mục cha phía trên Computer. Muốn dùng ứng dụng khác, chuyển cửa sổ; muốn trở về Android, dùng **Thoát môi trường Windows**, xác nhận rồi tự bật lại TalkBack. Thoát môi trường đóng các ứng dụng Windows đang chạy.

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
- Phần mở rộng NVDA chỉ ghi trạng thái sẵn sàng, mã tiến trình và thời gian hoạt động. Không lưu văn bản mà NVDA đọc. Khi chạy trên điện thoại, NVDA được gọi với `--no-logging`.
- NVDA phát tiếng không đồng nghĩa đọc đầy đủ mọi ứng dụng. Thông tin trợ năng và sự kiện tiêu điểm vẫn phụ thuộc Wine và từng phần mềm. Người dùng đã xác nhận bản trước đọc được khi yêu cầu đọc cửa sổ, nhưng điều hướng còn im lặng. Chế độ cử chỉ và đường phản hồi mới vẫn cần thử trên điện thoại Wine/Box64; kết quả máy Linux không thay thế bước đó.

## Kiểm tra trước khi phát hành

Workflow dựng APK phải kiểm tra gói, chạy cửa sổ Windows thật của cầu nối cũ, chạy **NVDA thật** trong Wine, nhận trạng thái từ NVDA và thu được tín hiệu âm thanh ở đầu ra thử nghiệm. Bài thử còn yêu cầu lệnh Down đổi lựa chọn ListBox thật và NVDA đọc Beta, Tab/Shift+Tab đổi tiêu điểm, Enter kích hoạt, Space đổi trạng thái, nhập được tiếng Việt và không lộ mật khẩu. Bài thử mới còn chạy chính WFM: Computer phải đọc ổ đĩa, đổi lựa chọn và mở bằng Enter; thư mục kiểm thử phải đọc Alpha/Beta, mở tệp bên trong, đi lên thư mục cha, đổi vùng bằng Tab/Shift+Tab và đi tới địa chỉ được nhập. Sau đó mới chạy kiểm thử Android, xác minh gói NVDA trong APK và kiểm tra chữ ký. Kiểm tra tương thích Wine/NVDA và dựng APK hiện dùng chung `.github/workflows/accessibility-apk.yml`; quy trình dò riêng đã được bỏ để tránh chạy trùng. Bước `probe.py --require-ready` phải xác nhận khởi tạo, âm thanh và các kiểm tra bắt buộc trước khi dựng APK.

Nhật ký và âm thanh của bài thử chỉ dùng dữ liệu thử nghiệm. Người dùng không cần gửi mật khẩu hoặc nhật ký có nội dung riêng tư để báo lỗi; có thể báo câu trạng thái trong bảng NVDA và ứng dụng Windows đang mở.
