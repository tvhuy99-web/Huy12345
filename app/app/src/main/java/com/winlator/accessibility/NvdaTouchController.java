package com.winlator.accessibility;

import android.graphics.*;
import android.os.*;
import android.speech.tts.TextToSpeech;
import android.view.*;
import android.widget.FrameLayout;
import com.winlator.R;
import com.winlator.XServerDisplayActivity;
import java.util.*;

/** Raw touch while Android touch exploration is off. Profiles never alter overlay controls. */
public final class NvdaTouchController implements AutoCloseable {
    private enum Mode { NORMAL, MENU, KEYBOARD, FUNCTIONS, DIGITS, EXIT }
    private final XServerDisplayActivity activity;private final NvdaController nvda;
    private final Handler main=new Handler(Looper.getMainLooper());
    private final Surface surface;private final NvdaGestureRecognizer gestures;
    private final NvdaTouchDispatcher touchInput;
    private final NvdaModifierState modifiers=new NvdaModifierState();
    private final ArrayDeque<String> menuStack=new ArrayDeque<>(),menuSources=new ArrayDeque<>();
    private TextToSpeech rescueVoice;private boolean closed,active=true,enabled,rescueReady;
    private Mode mode=Mode.NORMAL;
    private int selection,group,character,voiceGeneration;
    private String pendingRescue,profileData="";
    private String currentGesture="chưa có";
    private String lastMultiGesture="chưa có",lastMultiAction="chưa có";
    private NvdaGestureBindings bindings=new NvdaGestureBindings("");
    private static final String[] ROOT={"navigation","editing","keys","reading","windows_group","tools","exit","close"};
    private static final Map<String,String[]> MENUS=new LinkedHashMap<>();
    static {
        MENUS.put("navigation",new String[]{"up","down","left","right","tab","shift_tab","enter","space","escape","home","end","page_up","page_down"});
        MENUS.put("editing",new String[]{"select_all","copy","cut","paste","key:Ctrl+Z","key:Ctrl+Y","key:Ctrl+F","key:Ctrl+S","backspace","delete"});
        MENUS.put("keys",new String[]{"hold_ctrl","hold_alt","hold_shift","hold_windows","cancel_modifiers","function_keys","digit_keys","keyboard","key:F2","key:F5"});
        MENUS.put("reading",new String[]{"focus","window","read_all","repeat_last","copy_last","silence","nvda_menu"});
        MENUS.put("windows_group",new String[]{"windows","files","alt_tab","alt_shift_tab","desktop","start_menu","key:Alt+F4"});
        MENUS.put("tools",new String[]{"help","gesture_diagnostics","restart","disable"});
    }
    private static final String[] ALPHABETS={"abcdefghijklmnopqrstuvwxyz","ABCDEFGHIJKLMNOPQRSTUVWXYZ","0123456789",
        "ăâđêôơưáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ",
        ".,:;!?@#%&*()-_+=/\\\"'"};
    private final int[] groupNames={R.string.nvda_lowercase,R.string.nvda_uppercase,R.string.nvda_digits,R.string.nvda_vietnamese_characters,R.string.nvda_symbols};
    public NvdaTouchController(XServerDisplayActivity activity,NvdaController nvda,FrameLayout root) {
        this.activity=activity;this.nvda=nvda;
        gestures=new NvdaGestureRecognizer(main,activity.getResources().getDisplayMetrics().density,this::gesture);
        touchInput=new NvdaTouchDispatcher(gestures,root::requestDisallowInterceptTouchEvent);
        surface=new Surface();surface.setVisibility(View.GONE);surface.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        root.addView(surface,new FrameLayout.LayoutParams(-1,-1));
        rescueVoice=new TextToSpeech(activity,status->main.post(()->{
            if(closed||status!=TextToSpeech.SUCCESS)return;
            rescueReady=rescueVoice.setLanguage(new Locale("vi","VN"))>=TextToSpeech.LANG_AVAILABLE;
            if(rescueReady&&pendingRescue!=null) {String text=pendingRescue;pendingRescue=null;rescue(text);}
        }));
    }
    public boolean isEnabled() {return enabled&&active&&!closed;}
    public void update(boolean exploration) {
        boolean next=active&&!exploration&&activity.getPreferences().getBoolean(NvdaController.TOUCH_MODE,true);
        if(next==enabled)return;
        enabled=next;touchInput.cancel();mode=Mode.NORMAL;menuStack.clear();modifiers.clear();surface.setVisibility(next?View.VISIBLE:View.GONE);
        if(next) {surface.releasePointerCapture();announce(activity.getString(R.string.nvda_touch_started));}
        else {voiceGeneration++;pendingRescue=null;rescueVoice.stop();}
    }
    public void setActive(boolean active,boolean exploration) {this.active=active;update(exploration);if(!active)modifiers.clear();}
    public boolean dispatchTouchEvent(MotionEvent event) {
        return touchInput.dispatch(event,isEnabled()&&activity.hasWindowFocus()&&!activity.isFinishing());
    }
    public void cancelTouchInput() {touchInput.cancel();modifiers.clear();}
    public void openMenu() {openMenu("nút Quay lại");}
    private void openMenu(String source) {
        if(!isEnabled())return;
        if(menuSources.size()==4)menuSources.removeFirst();
        menuSources.addLast(source);
        gestures.cancel();modifiers.interruptSequence();mode=Mode.MENU;menuStack.clear();selection=0;
        surface.invalidate();announce("Menu điều khiển. "+item());
    }
    private String[] menuItems() {return menuStack.isEmpty()?ROOT:MENUS.get(menuStack.peek());}
    private String actionLabel(String action) {
        switch(action) {
            case "navigation":return "Điều hướng";case "editing":return "Chỉnh sửa";case "keys":return "Phím";
            case "reading":return "Đọc màn hình";case "windows_group":return "Cửa sổ";case "tools":return "Công cụ";
            case "disable":return "Tắt cử chỉ";case "close":return "Trở lại Windows";
            default:return NvdaGestureBindings.actionLabel(action);
        }
    }
    private String item() {String[] items=menuItems();return actionLabel(items[selection])+". "+(selection+1)+" / "+items.length;}
    private void announce(String text) {
        int request=++voiceGeneration;boolean speech=nvda.hasSpeech();
        nvda.command("message",text,ok->{if(!closed&&isEnabled()&&request==voiceGeneration&&(!ok||!speech))rescue(text);});
    }
    private void rescue(String text) {if(isEnabled()) {if(rescueReady)rescueVoice.speak(text,TextToSpeech.QUEUE_FLUSH,null,"nvda-rescue");else pendingRescue=text;}}
    private void command(String action) {command(action,"");}
    private void command(String action,String text) {nvda.command(action,text,ok->{if(!ok&&isEnabled())rescue(activity.getString(R.string.nvda_command_failed));});}
    private void key(String value) {
        try {
            NvdaShortcut shortcut=modifiers.consume(NvdaShortcut.parse(value));
            nvda.shortcut(shortcut,ok->{
                if(!ok&&isEnabled())rescue(activity.getString(R.string.nvda_command_failed));
                else if(ok&&isEnabled()&&shortcut.modifiers.isEmpty()&&Arrays.asList("control","windows","alt","shift").contains(shortcut.key))announce("Đã nhấn "+shortcut.display()+".");
            });
        }catch(IllegalArgumentException e) {modifiers.clear();announce(activity.getString(R.string.nvda_gesture_invalid_shortcut));}
    }
    private void normal(boolean keepModifiers) {mode=Mode.NORMAL;menuStack.clear();if(!keepModifiers)modifiers.clear();surface.invalidate();}
    private void leaveOverlay() {
        boolean held=modifiers.isHeld();normal(false);announce(activity.getString(R.string.nvda_touch_return)+(held?". Đã nhả các phím.":""));
    }
    private void gesture(int fingers,String kind) {
        if(!isEnabled())return;
        currentGesture=NvdaGestureBindings.id(fingers,kind);
        if(mode!=Mode.NORMAL) {overlay(fingers,kind);return;}
        String profile=activity.getContainer().getExtra(NvdaGestureBindings.EXTRA);
        if(!profile.equals(profileData)) {profileData=profile;bindings=new NvdaGestureBindings(profile);}
        String id=NvdaGestureBindings.id(fingers,kind),action=bindings.action(id);
        if(fingers>=3) {lastMultiGesture=id;lastMultiAction=action.startsWith("key:")?"tổ hợp tùy chỉnh":action;}
        perform(action);
    }
    private void perform(String action) {
        if(action.startsWith("hold_")) {
            String modifier=action.substring(5);if(modifier.equals("ctrl"))modifier="control";
            NvdaModifierState.Effect effect=modifiers.toggle(modifier,SystemClock.uptimeMillis());
            String name=modifier.equals("control")?"Ctrl":modifier.equals("windows")?"Windows":modifier.equals("shift")?"Shift":"Alt";
            if(effect==NvdaModifierState.Effect.PRESS_ONCE) {modifiers.clear();key(modifier);}
            else announce(activity.getString(effect==NvdaModifierState.Effect.HELD?R.string.nvda_modifier_held:R.string.nvda_modifier_released,name));
            return;
        }
        modifiers.interruptSequence();
        String shortcut=shortcutFor(action);
        if(shortcut!=null) {key(shortcut);return;}
        switch(action) {
            case "none":return;
            case "menu":openMenu("phép gán "+currentGesture);return;
            case "cancel_modifiers":modifiers.clear();announce(activity.getString(R.string.nvda_modifiers_cleared));return;
            case "keyboard":mode=Mode.KEYBOARD;group=character=0;surface.invalidate();speakCharacter();return;
            case "function_keys":case "digit_keys":mode=action.equals("function_keys")?Mode.FUNCTIONS:Mode.DIGITS;selection=0;surface.invalidate();announce(selectedKey());return;
            case "gesture_diagnostics":copyDiagnostics();return;
            case "copy_last":nvda.copyRecentSpeech(ok->{if(!ok&&isEnabled())announce(activity.getString(R.string.nvda_no_recent_speech));});return;
            case "exit":modifiers.clear();mode=Mode.EXIT;surface.invalidate();announce(activity.getString(R.string.nvda_exit_confirm));return;
            case "restart":modifiers.clear();nvda.restart();rescue(activity.getString(R.string.nvda_starting));return;
            case "help":announce(activity.getString(R.string.nvda_touch_help));return;
            case "disable":
                modifiers.clear();rescue(activity.getString(R.string.nvda_touch_disabled));
                activity.getPreferences().edit().putBoolean(NvdaController.TOUCH_MODE,false).apply();main.postDelayed(activity::updateNvdaTouchMode,1800);return;
            default:command(action);
        }
    }
    private static String shortcutFor(String action) {
        if(action.startsWith("key:"))return action.substring(4);
        switch(action) {
            case "up":case "down":case "left":case "right":case "tab":case "enter":case "escape":case "space":case "home":case "end":case "backspace":case "delete":return action;
            case "shift_tab":return "Shift+Tab";case "page_up":return "PageUp";case "page_down":return "PageDown";
            case "select_all":return "Ctrl+A";case "copy":return "Ctrl+C";case "cut":return "Ctrl+X";case "paste":return "Ctrl+V";
            case "alt_tab":return "Alt+Tab";case "alt_shift_tab":return "Alt+Shift+Tab";case "desktop":return "Windows+D";
            default:return null;
        }
    }
    private String selectedKey() {return mode==Mode.FUNCTIONS?"F"+(selection+1):String.valueOf(selection);}
    private void overlay(int fingers,String kind) {
        if(fingers==3&&kind.equals("tap")) {openMenu("chạm ba ngón trong bảng");return;}
        boolean escape=fingers==3&&kind.equals("left");
        if(escape) {
            if(mode==Mode.MENU&&!menuStack.isEmpty()) {menuStack.pop();selection=0;surface.invalidate();announce(item());}
            else {leaveOverlay();}
            return;
        }
        if(mode==Mode.EXIT) {if(fingers==1&&kind.equals("double"))activity.exitFromNvdaTouch();else announce(activity.getString(R.string.nvda_exit_confirm));return;}
        if(mode==Mode.KEYBOARD) {
            if(fingers==1&&(kind.equals("up")||kind.equals("down"))) {group=Math.floorMod(group+(kind.equals("down")?1:-1),ALPHABETS.length);character=0;speakCharacter();}
            else if(fingers==1&&(kind.equals("right")||kind.equals("left"))) {character=Math.floorMod(character+(kind.equals("right")?1:-1),ALPHABETS[group].length());speakCharacter();}
            else if(fingers==1&&kind.equals("double")) {
                String text=String.valueOf(ALPHABETS[group].charAt(character));
                if(modifiers.isHeld())key(text);else command("text",text);
            }else if(fingers==3&&kind.equals("right"))key("Space");
            else if(fingers==2&&(kind.equals("up")||kind.equals("down")))key(kind.equals("up")?"Tab":"Shift+Tab");
            else if(fingers==2&&kind.equals("right"))key("Backspace");
            else if(fingers==2&&kind.equals("double"))command("window");
            else if(fingers==1&&kind.equals("tap"))speakCharacter();
            return;
        }
        if(fingers==1&&(kind.equals("up")||kind.equals("down")||kind.equals("left")||kind.equals("right"))) {
            int count=mode==Mode.MENU?menuItems().length:mode==Mode.FUNCTIONS?12:10;
            selection=Math.floorMod(selection+(kind.equals("down")||kind.equals("right")?1:-1),count);
            surface.invalidate();announce(mode==Mode.MENU?item():selectedKey());
        }else if(fingers==1&&kind.equals("double")) {
            if(mode==Mode.MENU) {
                String action=menuItems()[selection];
                if(MENUS.containsKey(action)) {menuStack.push(action);selection=0;surface.invalidate();announce(item());}
                else if(action.equals("close")) {leaveOverlay();}
                else {normal(true);perform(action);}
            }else {String value=selectedKey();normal(true);key(value);}
        }else if(fingers==1&&kind.equals("tap"))announce(mode==Mode.MENU?item():selectedKey());
    }
    public void copyDiagnostics() {
        android.view.accessibility.AccessibilityManager accessibility=(android.view.accessibility.AccessibilityManager)activity.getSystemService(android.content.Context.ACCESSIBILITY_SERVICE);
        String details="Cử chỉ đang bật: "+isEnabled()+"; khám phá bằng chạm: "+(accessibility!=null&&accessibility.isTouchExplorationEnabled())
            +"\nCử chỉ nhiều ngón gần nhất: "+lastMultiGesture+"; phép gán: "+lastMultiAction
            +"\nNguồn mở menu: "+(menuSources.isEmpty()?"chưa mở":String.join(" -> ",menuSources))+"\n"+gestures.diagnostics();
        int result=NvdaGestureDiagnostics.copy(activity,details)?R.string.nvda_gesture_diagnostics_copied:R.string.nvda_gesture_diagnostics_failed;
        if(isEnabled())announce(activity.getString(result));
        else android.widget.Toast.makeText(activity,result,android.widget.Toast.LENGTH_SHORT).show();
    }
    private void speakCharacter() {surface.invalidate();announce(activity.getString(groupNames[group])+". "+ALPHABETS[group].charAt(character));}
    private final class Surface extends View {
        private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        Surface() {super(activity);setKeepScreenOn(true);}
        @Override public boolean onTouchEvent(MotionEvent event) {return NvdaTouchController.this.dispatchTouchEvent(event);}
        @Override protected void onDraw(Canvas canvas) {
            if(mode==Mode.NORMAL)return;
            canvas.drawColor(0xED101820);paint.setColor(Color.WHITE);paint.setTextSize(20*getResources().getDisplayMetrics().scaledDensity);
            String title=mode==Mode.EXIT?activity.getString(R.string.nvda_exit_environment):mode==Mode.KEYBOARD?
                activity.getString(groupNames[group])+": "+ALPHABETS[group].charAt(character):mode==Mode.MENU?actionLabel(menuItems()[selection]):selectedKey();
            canvas.drawText(title,24,getHeight()/2f,paint);
        }
    }
    @Override public void close() {if(closed)return;closed=true;voiceGeneration++;modifiers.clear();touchInput.cancel();main.removeCallbacksAndMessages(null);rescueVoice.stop();rescueVoice.shutdown();surface.setVisibility(View.GONE);}
}
