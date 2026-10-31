# Sửa mã tiếng Trung của Zetianji trên Winlator (31/10/2026)

## Kết quả APK 53
Nhật ký OnePlus của APK 53 xác nhận phần khởi động game vẫn hoạt động: cửa sổ Zetianji hiện và nhận tiêu điểm, NVDA vào được ListBox. Tuy nhiên Wine vẫn báo `codePages.ansi=1252`, `oem=437`, `systemLCID=1033`, `userLCID=1033`, và NVDA vẫn nhận chuỗi GBK bị giải mã theo bảng mã Tây Âu. Vì vậy chỉ đặt `LC_ALL=zh_CN.UTF-8` và FontAssoc chưa đủ.

## APK 54: vá tầng khởi tạo locale của Wine
Bản thử mới giữ nguyên bản sửa CPU và bổ sung một bản vá **hash-pinned, có hoàn nguyên** cho Wine 10.10 đi kèm Winlator:

- Tệp: `/opt/wine/lib/wine/x86_64-unix/ntdll.so`
- SHA-256 gốc: `8e56504a870c8b00ac76df8540c73f26cd33af96ca682600b750721cdde296ca`
- Offset: `0x1192a`
- Byte gốc: `75 3c`
- Byte khi profile CP936 bật: `eb 00`
- SHA-256 sau vá: `1d2708d8eaea7c73cde30b3d2b6f3607f64f3fca39c2a62973a7c0406d1dade4`

Nhánh lệnh này thuộc `unix_to_win_locale()`. Khi profile CP936 bật, bản vá buộc Wine dùng `LC_ALL` do Winlator cung cấp thay vì giữ locale host/English đã được `setlocale()` trả về. Khi profile tắt, Winlator hoàn nguyên đúng hai byte. Binary khác SHA sẽ bị từ chối, không sửa.

Profile CP936 đồng thời đặt:
- `LC_ALL=zh_CN.UTF-8`
- `LANG=zh_CN.UTF-8`
- `LANGUAGE=zh_CN:zh`
- `LC_CTYPE=zh_CN.UTF-8`
- `LC_MESSAGES=zh_CN.UTF-8`

Cấu hình `ANSI(00)=yes` trong Wine FontAssoc vẫn được giữ để GDI dùng ACP đang hoạt động thay vì mặc định 1252.

## Cách bật và thử
1. Cài APK 54 được build và ký thành công từ nhánh `codex/accessibility-apk`.
2. Đóng hoàn toàn môi trường Windows/Winlator.
3. Mở **Môi trường → Sửa → Cấu hình Wine → Ngôn ngữ ứng dụng Windows (Wine locale)**.
4. Chọn **Tiếng Trung giản thể (Trung Quốc) - CP936** và lưu.
5. Mở lại môi trường hoàn toàn, sau đó chạy Zetianji đã có bản sửa CPU.
6. Chia sẻ nhật ký công cụ.

Nhật ký APK 54 phải có:
- `[wine.locale.binary]` với `profile=zh_CN`, `state=enabled` hoặc `already-enabled`, SHA bản vá.
- `[wine.locale.environment]` với các biến zh_CN nêu trên.
- Khi vào game, `codePages.ansi` kỳ vọng là **936** và `systemLCID/userLCID` kỳ vọng là **2052**.
- NVDA kỳ vọng nhận chữ Trung thật, không còn chuỗi kiểu `¿ÉÓÃ...`.

Nếu `wine.locale.binary` báo `unsupported-binary`, không tiếp tục vá binary đó. Nếu binary đã bật nhưng `GetACP` vẫn là 1252, bước tiếp theo sẽ là xác minh đường locale bên trong Wine bằng probe riêng thay vì sửa game EXE.

## Hoàn tác
Chọn **Mặc định (theo Winlator)**, lưu và đóng/mở lại môi trường. Winlator sẽ:
1. hoàn nguyên hai byte `ntdll.so` nếu đúng SHA bản vá;
2. khôi phục `ANSI(00)` về giá trị trước đó nếu vẫn là giá trị do Winlator đặt;
3. không đụng tới bản vá CPU trong `zetianji.exe`.

## Kiểm thử
- Unit test kiểm tra biến môi trường CP936 và quyền ưu tiên của biến người dùng.
- Robolectric đọc chính `assets/rootfs.tzst`, xác nhận SHA-256 và byte mục tiêu của `ntdll.so`.
- GitHub Actions phải hoàn tất Wine/NVDA tests, Android tests, build APK và kiểm tra chữ ký trùng APK 52 trước khi release.
