package com.winlator.accessibility;

import org.json.JSONObject;
import java.util.*;

/** A complete per-environment profile. Only differences from defaults are persisted. */
public final class NvdaGestureBindings {
    public static final String EXTRA="nvda_gestures";
    public static final String[] DIRECTIONS={"up","down","left","right"};
    public static final String[] ACTIONS={"none","up","down","left","right","tab","shift_tab","enter","space","escape",
        "hold_ctrl","hold_windows","hold_alt","hold_shift","cancel_modifiers","menu","function_keys","digit_keys","keyboard",
        "focus","window","read_all","inspect_controls","object_next","object_previous","object_activate","dialog_details","repeat_last","copy_last","silence","nvda_menu","windows","files","desktop","start_menu","close_window",
        "alt_tab","alt_shift_tab","game_show","game_inspect","game_voice_enable","game_voice_restore","home","end","page_up","page_down","backspace","delete","select_all","copy","cut","paste",
        "key:Ctrl+Z","key:Ctrl+Y","key:Ctrl+F","key:Ctrl+S","key:Alt+F4","key:F2","key:F5","help","gesture_diagnostics","export_diagnostics","restart","exit"};
    private static final LinkedHashMap<String,String> DEFAULTS=new LinkedHashMap<>();
    static {
        for(int fingers=1;fingers<=4;fingers++) {
            for(String direction:DIRECTIONS)DEFAULTS.put(id(fingers,direction),"none");
            if(fingers==1)for(String first:DIRECTIONS)for(String second:DIRECTIONS)if(!first.equals(second))DEFAULTS.put(id(1,first+"_"+second),"none");
            for(String tap:new String[]{"tap","double","triple"})DEFAULTS.put(id(fingers,tap),"none");
        }
        defaults(1,new String[]{"up","down","left","right","tap","double"},new String[]{"up","down","left","right","silence","enter"});
        defaults(2,new String[]{"up","down","left","right","tap","double"},new String[]{"tab","shift_tab","hold_ctrl","hold_windows","focus","window"});
        defaults(3,new String[]{"up","down","left","right","tap","double"},new String[]{"function_keys","digit_keys","escape","space","menu","repeat_last"});
        defaults(4,new String[]{"up","down","left","right","tap"},new String[]{"desktop","copy_last","alt_tab","alt_shift_tab","none"});
    }
    private static void defaults(int fingers,String[] gestures,String[] actions) {for(int i=0;i<gestures.length;i++)DEFAULTS.put(id(fingers,gestures[i]),actions[i]);}
    public static String id(int fingers,String gesture) {return fingers+":"+gesture;}
    public static List<String> gestures() {return new ArrayList<>(DEFAULTS.keySet());}
    private final Map<String,String> overrides=new LinkedHashMap<>();
    public NvdaGestureBindings(String data) {
        if(data==null || data.length()>16384)return;
        try {
            JSONObject document=new JSONObject(data);if(document.optInt("version")!=1)return;
            JSONObject values=document.optJSONObject("mappings");if(values==null)return;
            for(String id:DEFAULTS.keySet())if(values.has(id))try {set(id,values.getString(id));}catch(Exception ignored) { }
        } catch(Exception ignored) { }
    }
    public String action(String id) {return overrides.containsKey(id)?overrides.get(id):DEFAULTS.getOrDefault(id,"none");}
    public void set(String id,String action) {
        if(!DEFAULTS.containsKey(id))throw new IllegalArgumentException();
        String value=action;
        if(value.startsWith("key:"))value="key:"+NvdaShortcut.parse(value.substring(4)).display();
        else if(!Arrays.asList(ACTIONS).contains(value))throw new IllegalArgumentException();
        if(value.equals(DEFAULTS.get(id)))overrides.remove(id);else overrides.put(id,value);
    }
    public void reset() {overrides.clear();}
    public String json() {
        try {return new JSONObject().put("version",1).put("mappings",new JSONObject(overrides)).toString();}
        catch(Exception e) {throw new IllegalStateException(e);}
    }
    public static String gestureLabel(String id) {
        String[] parts=id.split(":",2);String count=parts[0];String kind=parts[1];
        if(kind.equals("tap") || kind.equals("double") || kind.equals("triple"))return "Chạm "+(kind.equals("tap")?"một":kind.equals("double")?"hai":"ba")+" lần bằng "+count+" ngón tay";
        String[] legs=kind.split("_");return "Vuốt "+direction(legs[0])+(legs.length>1?" rồi "+direction(legs[1]):"")+" bằng "+count+" ngón tay";
    }
    private static String direction(String value) {switch(value) {case "up":return "lên";case "down":return "xuống";case "left":return "sang trái";default:return "sang phải";}}
    public static String shortcutFor(String action) {
        if(action.startsWith("key:"))return action.substring(4);
        switch(action) {
            case "up":case "down":case "left":case "right":case "tab":case "enter":case "escape":case "space":case "home":case "end":case "backspace":case "delete":return action;
            case "shift_tab":return "Shift+Tab";case "page_up":return "PageUp";case "page_down":return "PageDown";
            case "select_all":return "Ctrl+A";case "copy":return "Ctrl+C";case "cut":return "Ctrl+X";case "paste":return "Ctrl+V";
            case "alt_tab":return "Alt+Tab";case "alt_shift_tab":return "Alt+Shift+Tab";case "desktop":return "Windows+D";
            default:return null;
        }
    }
    public static String actionLabel(String action) {
        if(action.startsWith("key:"))return NvdaShortcut.parse(action.substring(4)).display();
        switch(action) {
            case "none":return "Không gán";
            case "up":return "Mũi tên lên";case "down":return "Mũi tên xuống";case "left":return "Mũi tên trái";case "right":return "Mũi tên phải";
            case "tab":return "Tab";case "shift_tab":return "Shift+Tab";case "enter":return "Enter";case "space":return "Phím cách";case "escape":return "Escape";
            case "hold_ctrl":return "Ctrl";case "hold_windows":return "Windows";case "hold_alt":return "Alt";case "hold_shift":return "Shift";
            case "cancel_modifiers":return "Nhả các phím đang giữ";
            case "menu":return "Menu điều khiển";case "function_keys":return "Bảng F1–F12";case "digit_keys":return "Bảng số 0–9";case "keyboard":return "Bàn phím chữ";
            case "inspect_controls":return "Duyệt thành phần";case "object_next":return "Thành phần tiếp theo";case "object_previous":return "Thành phần trước";case "object_activate":return "Kích hoạt thành phần";case "dialog_details":return "Đọc đầy đủ thông báo";
            case "focus":return "Đọc mục hiện tại";case "window":return "Đọc cửa sổ hiện tại";case "read_all":return "Đọc liên tục";
            case "repeat_last":return "Đọc lại câu gần nhất";case "copy_last":return "Sao chép câu gần nhất";case "silence":return "Ngắt lời đọc";
            case "nvda_menu":return "Trình đơn NVDA";case "windows":return "Danh sách cửa sổ";case "files":return "Trình quản lý tệp";
            case "game_show":return "Hiện cửa sổ ứng dụng vừa mở";
            case "game_voice_enable":return "Chuẩn bị nhật ký cho game đã chọn";
            case "game_inspect":return "Kiểm tra ứng dụng vừa mở";
            case "game_voice_restore":return "Khôi phục bộ giọng game";
            case "close_window":return "Đóng cửa sổ";case "desktop":return "Windows+D";case "start_menu":return "Trình đơn Start";case "alt_tab":return "Alt+Tab";case "alt_shift_tab":return "Alt+Shift+Tab";
            case "home":return "Home";case "end":return "End";case "page_up":return "Page Up";case "page_down":return "Page Down";
            case "backspace":return "Backspace";case "delete":return "Delete";case "select_all":return "Ctrl+A";case "copy":return "Ctrl+C";case "cut":return "Ctrl+X";case "paste":return "Ctrl+V";
            case "gesture_diagnostics":return "Sao chép nhật ký công cụ";
            case "export_diagnostics":return "Chia sẻ nhật ký công cụ";
            case "help":return "Hướng dẫn cử chỉ";case "restart":return "Khởi động lại NVDA";case "exit":return "Thoát môi trường";
            default:throw new IllegalArgumentException();
        }
    }
}
