<p align="center">
	<img src="logo.png" width="376" height="128" alt="Winlator Logo" />
</p>

<p align="center">
	<a href="https://winlator.org/">
		<img src="https://img.shields.io/badge/winlator-website-42a5f5?style=flat-square" />
	</a>
	<a href="https://github.com/brunodev85/winlator/releases">
		<img src="https://img.shields.io/github/downloads/brunodev85/winlator/v11.2.0/total.svg?style=flat-square&label=downloads@v11.2" />
	</a>
	<a href="https://github.com/brunodev85/winlator/stargazers">
		<img src="https://img.shields.io/github/stars/brunodev85/winlator?style=flat-square&logo=github&color=ffb300" />
	</a>
</p>

# Winlator

**Kho phát triển chính:** Toàn bộ mã ứng dụng, Gladio và Vortek được lưu trực tiếp trong kho này. Dự án Android nằm trong [app/](app/). Xem [ghi chú tiếng Việt](VIETNAMESE.md) và [nguồn gốc mã](SOURCE_ORIGINS.md). APK thử nghiệm được đăng tại [Releases](https://github.com/tvhuy99-web/Huy12345/releases).

Winlator is an Android application that lets you to run Windows (x86_64) applications with Wine and Box86/Box64.

# Cài đặt bản thử nghiệm

1. Mở [Releases của kho này](https://github.com/tvhuy99-web/Huy12345/releases) và tải tệp **Winlator-VI-NVDA.apk** ở bản NVDA thử nghiệm mới nhất. Tệp **Winlator-VI-accessibility.apk** thuộc các bản cầu nối TalkBack trước đó.
2. Cài APK trên thiết bị Android 8 trở lên, ARM64. APK dùng chữ ký debug; nếu đang có Winlator với chữ ký khác, cần xử lý xung đột chữ ký và sao lưu dữ liệu trước khi thay bản cài.
3. Bật TalkBack và làm theo [hướng dẫn thử trợ năng](ACCESSIBILITY_TESTING.md). Trong ứng dụng có thể chọn **Cài đặt → Ngôn ngữ → Tiếng Việt**.
4. Khi khởi động môi trường, dùng **Trợ năng Windows (thử nghiệm)** để duyệt các mục được lấy từ cửa sổ Wine thật. Xem [hướng dẫn giai đoạn 2 và giới hạn](RUNTIME_ACCESSIBILITY.md).
5. Bản NVDA thử nghiệm tự khởi chạy trình đọc cùng môi trường. Khi người dùng tự tắt TalkBack, có thể điều khiển bằng cử chỉ: vuốt một ngón lên/xuống là mũi tên, trái/phải là Shift+Tab/Tab, chạm hai lần là Enter, chạm ba ngón mở menu giọng nói. Xem [hướng dẫn NVDA, tùy chọn tự chạy và giới hạn](NVDA_INTEGRATION.md).


----

[![Play on Youtube](https://img.youtube.com/vi/ETYDgKz4jBQ/3.jpg)](https://www.youtube.com/watch?v=ETYDgKz4jBQ)
[![Play on Youtube](https://img.youtube.com/vi/9E4wnKf2OsI/2.jpg)](https://www.youtube.com/watch?v=9E4wnKf2OsI)
[![Play on Youtube](https://img.youtube.com/vi/czEn4uT3Ja8/2.jpg)](https://www.youtube.com/watch?v=czEn4uT3Ja8)
[![Play on Youtube](https://img.youtube.com/vi/eD36nxfT_Z0/2.jpg)](https://www.youtube.com/watch?v=eD36nxfT_Z0)
[![Play on Youtube](https://img.youtube.com/vi/GHBKmzGmhoo/1.jpg)](https://www.youtube.com/watch?v=GHBKmzGmhoo)

----

# Useful Tips

- If you are experiencing instability issues, try changing the Box64 preset in Container Settings -> Advanced Tab.
- For applications that use .NET Framework, try installing `Wine Mono` found in Start Menu -> System Tools -> Installers.
- If some older games don't open, try adding the environment variable `MESA_EXTENSION_MAX_YEAR=2003` in Container Settings -> Environment Variables.
- Try running the games using the shortcut on the Winlator home screen, there you can define individual settings for each game.
- To display low resolution games correctly, try to enabling the `Force Fullscreen` option in the shortcut settings.
- To improve stability in games that uses Unity Engine, try changing the Box64 preset to `Stability` or in the shortcut settings add the exec argument `-force-gfx-direct`.
- If you are experiencing audio crackling, try increasing the average latency in ALSA/PulseAudio configuration. Old games like Unreal Gold resolve audio issues by increasing this value to 90ms.

# Credits and Third-party apps

- GLIBC Patches by [Termux Pacman](https://github.com/termux-pacman/glibc-packages)
- Wine ([winehq.org](https://www.winehq.org/))
- Box86/Box64 by [ptitseb](https://github.com/ptitSeb)
- Mesa (Turnip/Zink/VirGL) ([mesa3d.org](https://www.mesa3d.org))
- DXVK ([github.com/doitsujin/dxvk](https://github.com/doitsujin/dxvk))
- VKD3D ([gitlab.winehq.org/wine/vkd3d](https://gitlab.winehq.org/wine/vkd3d))
- CNC DDraw ([github.com/FunkyFr3sh/cnc-ddraw](https://github.com/FunkyFr3sh/cnc-ddraw))

Special thanks to all the developers involved in these projects.<br>
Thank you to all the people who believe in this project.
