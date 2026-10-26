# Trợ năng khi môi trường Wine đang chạy — bản thử nghiệm

Mục tiêu của bản này là đưa **các mục thật của cửa sổ Windows đang mở** sang giao diện Android mà TalkBack có thể duyệt và điều khiển. Đây là bước thử nghiệm đầu của giai đoạn 2, chưa phải cam kết mọi ứng dụng Windows hoặc game đều dùng được.

## Thử trực tiếp trên điện thoại

1. Cài APK thử mới nhất trong [Releases](https://github.com/tvhuy99-web/Huy12345/releases). Giữ và sao lưu dữ liệu trước nếu Android báo khác chữ ký với Winlator đang cài.
2. Bật TalkBack rồi khởi động một môi trường. Sau khi xuất hiện cửa sổ Wine đầu tiên, bảng **Trợ năng Windows (thử nghiệm)** sẽ tự mở. Nếu chưa mở, tìm nút cùng tên ở góc trên hoặc nhấn Quay lại để mở menu Winlator rồi chọn mục này.
3. Chờ thông báo **Đã kết nối với Wine**. Nếu chưa kết nối, đợi môi trường khởi động xong rồi chọn **Kết nối lại với Wine**.
4. Chọn **Mở bài thử trợ năng Windows**. Đây là cửa sổ Win32 thật chạy trong Wine, không phải giao diện giả trong Android.
5. Duyệt tới ô **Tên thử**, nhấn đúp, nhập `Tiếng Việt 123`, chọn **Áp dụng vào Windows**. Đọc lại để kiểm tra giá trị.
6. Duyệt tới **Đồng ý**, nhấn đúp và kiểm tra TalkBack báo đã chọn. Duyệt tới **Tiếp tục**, kích hoạt và tìm dòng **Đã kích hoạt**.
7. Kiểm tra ô mật khẩu được báo có nội dung ẩn; nút **Disabled control** không thể kích hoạt.
8. Chọn **Chọn cửa sổ Windows** để chuyển sang ứng dụng hoặc trình cài đặt của bạn. Các mục của cửa sổ đó sẽ được cập nhật trong bảng. Dùng thao tác nhấn giữ/nhấn đúp và giữ của TalkBack để đặt tiêu điểm Windows vào một mục, rồi chọn **Gửi phím Windows** nếu cần Tab, Enter, phím mũi tên hoặc phím cách.
9. **Trở lại hình ảnh màn hình máy tính** đóng bảng, vẫn giữ môi trường chạy. Nút Trợ năng Windows cho phép mở lại. Tính năng không cần tài khoản, máy chủ hoặc mạng Internet.

Chữ do ứng dụng Windows cung cấp giữ nguyên ngôn ngữ của ứng dụng đó. Phần tiếng Việt là giao diện cầu nối và thông báo; việc dịch Android không tự dịch phần mềm bên trong Wine.

## Những gì đã được triển khai

- Chương trình Windows 64 bit viết bằng C, biên dịch từ [bridge.c](runtime-accessibility/bridge.c), được APK chép vào `C:\windows\winlator-a11y.exe` của môi trường đang dùng.
- Thu thập cây MSAA bằng `AccessibleObjectFromWindow` và `AccessibleChildren`; đọc thêm điều khiển Win32 tiêu chuẩn khi chúng chưa có trong cây. Bổ sung tên, giá trị, loại, trạng thái chọn/khóa và cửa sổ đang hoạt động.
- Thực hiện hành động mặc định MSAA hoặc bấm nút Win32 bằng API của điều khiển. Sửa văn bản qua MSAA/Win32, đặt tiêu điểm, chuyển cửa sổ và gửi một tập phím giới hạn. Không đoán tọa độ rồi bấm lên ảnh.
- Giao diện Android gồm các mục có tiêu điểm trợ năng, cập nhật tại chỗ khi có thể. Bản này sử dụng bảng danh sách, **chưa có thao tác chạm khám phá trực tiếp theo vị trí trên ảnh desktop**.
- Tự mở bảng khi TalkBack đang bật lúc môi trường xuất hiện; tránh để chế độ bắt chuột giành tiêu điểm của TalkBack. Có đường vào qua menu và nút hiển thị khi bật khám phá bằng chạm.
- Giao tiếp TCP chỉ trên `127.0.0.1`, cổng ngẫu nhiên và mã xác thực ngẫu nhiên theo phiên. Giới hạn kích thước khung, số mục, độ sâu cây và độ dài văn bản. Không lưu nội dung cửa sổ vào nhật ký.
- Lệnh gắn với phiên bản giao diện; từ chối lệnh khi giao diện hoặc cửa sổ đang hoạt động đã thay đổi. Mật khẩu không được lấy giá trị, không hiện nội dung và không sửa qua bảng này.
- Tác vụ đọc/ghi chạy ngoài luồng Android chính. Chương trình hỗ trợ kết thúc khi mất kết nối hoặc môi trường dừng.

## Giới hạn cần kiểm tra tiếp

- Chưa có kết quả chạy trên điện thoại ARM64 với Wine/Box64 và TalkBack thực tế. Kiểm thử Wine trên máy Linux không thay thế được bước này.
- Bản này dùng **MSAA + Win32**, chưa triển khai UI Automation đầy đủ, IAccessible2, OCR hoặc trình đọc màn hình trong game. Không được suy ra mọi trình cài đặt đều tương thích chỉ vì bài thử thành công.
- Điều khiển tự vẽ bằng DirectX/OpenGL hoặc không xuất thông tin trợ năng có thể chỉ trả về một cửa sổ trống. Danh sách/tệp/cây thư mục phụ thuộc việc ứng dụng và Wine xuất được các mục con qua MSAA.
- Tên thiếu hoặc thứ tự đọc chưa đúng có thể đến từ nguồn MSAA. Cầu nối không tự đặt tên theo suy đoán.
- Quét giới hạn 256 mục, 12 cấp, có kiểm tra ngân sách thời gian giữa các lời gọi. Một lời gọi COM của ứng dụng bị treo vẫn có thể kéo dài hơn ngân sách; luồng Android chính không chờ nó và giao diện sẽ báo mất phản hồi khi hết thời gian kết nối.
- Cập nhật chủ yếu theo chu kỳ khoảng 0,8 giây khi bảng mở; khi đóng, nhịp chậm lại. Chưa đồng bộ sự kiện tiêu điểm Windows–TalkBack đầy đủ. Đang sửa một ô thì việc cửa sổ thay đổi có thể khiến lệnh bị từ chối; đọc lại ô mới rồi thử lại.
- Chưa hỗ trợ nhập mật khẩu qua bảng trợ năng, lựa chọn vùng văn bản, kéo thả, menu phức tạp hoặc tất cả hành động của hộp chọn. Phím Windows là đường bổ sung khi chương trình hỗ trợ bàn phím.

## Biên dịch và kiểm thử

Mọi mã mới vẫn ở kho `Huy12345`.

```bash
# Ubuntu, trên máy phát triển hoặc GitHub Actions; không cần làm trên điện thoại.
sudo apt-get install gcc-mingw-w64-x86-64 wine64 xvfb xauth fonts-wine
bash runtime-accessibility/build.sh
xvfb-run -a python3 runtime-accessibility/test_wine.py
cd app
bash gradlew testDebugUnitTest assembleDebug
```

Workflow [accessibility-apk.yml](.github/workflows/accessibility-apk.yml) biên dịch chương trình hỗ trợ, chạy nó trong Wine với cửa sổ thật, kiểm tra đọc tiếng Việt, nhập văn bản, bật ô đánh dấu, bấm nút, ẩn mật khẩu và từ chối thao tác không hợp lệ. Sau đó mới chạy các kiểm thử Android và dựng APK có chương trình hỗ trợ bên trong. Gradle từ chối đóng gói nếu thiếu chương trình hỗ trợ.

Các kiểm thử Android bao gồm tài nguyên/điều khiển của giai đoạn 1, giải mã khung UTF-8, giới hạn dữ liệu và kiểm tra cây trợ năng. Kết quả tự động nằm trong mục Actions của từng bản thử. Người thử trên điện thoại nên ghi lại tên ứng dụng, bản Wine, thao tác đã làm và câu TalkBack đọc khi gặp lỗi; không cần gửi dữ liệu mật khẩu.
