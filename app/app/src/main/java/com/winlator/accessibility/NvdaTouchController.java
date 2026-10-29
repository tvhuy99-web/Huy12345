package com.winlator.accessibility;

import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.os.Handler;
import android.os.Looper;
import android.speech.tts.TextToSpeech;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.View;
import android.widget.FrameLayout;
import com.winlator.R;
import com.winlator.XServerDisplayActivity;
import java.util.Locale;

/** Raw touch belongs to Windows here. This view is hidden whenever touch exploration is on. */
public final class NvdaTouchController implements AutoCloseable {
    private final XServerDisplayActivity activity;
    private final NvdaController nvda;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Surface surface;
    private final NvdaGestureRecognizer gestures;
    private TextToSpeech rescueVoice;
    private boolean closed, active=true, enabled, menu, keyboard, confirmingExit, rescueReady;
    private int selection, group, character, voiceGeneration;
    private String pendingRescue;
    private final String[] actions={"focus","window","nvda_menu","windows","files","desktop","start_menu","alt_tab","escape","space",
        "home","end","page_up","page_down","select_all","copy","paste","cut","backspace","delete",
        "keyboard","help","restart","disable","exit","close"};
    private final int[] labels={R.string.nvda_focus,R.string.nvda_window,R.string.nvda_menu,R.string.nvda_windows,R.string.nvda_files,R.string.nvda_desktop,R.string.nvda_start_menu,
        R.string.nvda_switch_window,R.string.nvda_escape,R.string.nvda_space,R.string.nvda_home,R.string.nvda_end,
        R.string.nvda_page_up,R.string.nvda_page_down,R.string.nvda_select_all,R.string.nvda_copy,R.string.nvda_paste,
        R.string.nvda_cut,R.string.nvda_backspace,R.string.nvda_delete,R.string.nvda_keyboard,R.string.nvda_gesture_help,
        R.string.nvda_restart,R.string.nvda_touch_disable,R.string.nvda_exit_environment,R.string.nvda_touch_return};
    private final String[] alphabets={"abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "0123456789",
        "ăâđêôơưáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ",
        ".,:;!?@#%&*()-_+=/\\\"'"};
    private final int[] groupNames={R.string.nvda_lowercase,R.string.nvda_uppercase,R.string.nvda_digits,
        R.string.nvda_vietnamese_characters,R.string.nvda_symbols};

    public NvdaTouchController(XServerDisplayActivity activity, NvdaController nvda, FrameLayout root) {
        this.activity=activity;this.nvda=nvda;
        gestures=new NvdaGestureRecognizer(main,activity.getResources().getDisplayMetrics().density,this::gesture);
        surface=new Surface();surface.setVisibility(View.GONE);surface.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        root.addView(surface,new FrameLayout.LayoutParams(-1,-1));
        rescueVoice=new TextToSpeech(activity,status->main.post(()-> {
            if(closed || status!=TextToSpeech.SUCCESS)return;
            int language=rescueVoice.setLanguage(new Locale("vi","VN"));
            rescueReady=language>=TextToSpeech.LANG_AVAILABLE;
            if(rescueReady && pendingRescue!=null) {String text=pendingRescue;pendingRescue=null;rescue(text);}
        }));
    }
    public boolean isEnabled() { return enabled && active && !closed; }
    public void update(boolean touchExploration) {
        boolean next=active && !touchExploration && activity.getPreferences().getBoolean(NvdaController.TOUCH_MODE,true);
        if(next==enabled)return;
        enabled=next;gestures.cancel();menu=keyboard=confirmingExit=false;
        surface.setVisibility(next?View.VISIBLE:View.GONE);
        if(next) {
            surface.releasePointerCapture();
            announce(activity.getString(R.string.nvda_touch_started));
        } else { voiceGeneration++;pendingRescue=null;rescueVoice.stop(); }
    }
    public void setActive(boolean active,boolean exploration) {this.active=active;update(exploration);}
    public void openMenu() {
        if(!isEnabled())return;
        gestures.cancel();keyboard=false;confirmingExit=false;menu=true;selection=0;
        surface.invalidate();announce(activity.getString(R.string.nvda_touch_menu)+". "+item());
    }
    private String item() {return activity.getString(labels[selection])+". "+(selection+1)+" / "+actions.length;}
    private void announce(String text) {
        int request=++voiceGeneration;
        boolean speech=nvda.hasSpeech();
        nvda.command("message",text,ok-> {
            if(!closed && enabled && active && request==voiceGeneration && (!ok || !speech))rescue(text);
        });
    }
    private void rescue(String text) {
        if(!closed && enabled && active) {
            if(rescueReady)rescueVoice.speak(text,TextToSpeech.QUEUE_FLUSH,null,"nvda-rescue");
            else pendingRescue=text;
        }
    }
    private void command(String action) {command(action,"");}
    private void command(String action,String text) {
        nvda.command(action,text,ok->{if(!ok && isEnabled())rescue(activity.getString(R.string.nvda_command_failed));});
    }
    private void leaveMenu() {
        menu=keyboard=confirmingExit=false;surface.invalidate();announce(activity.getString(R.string.nvda_touch_return));
    }
    private void gesture(int fingers,String kind) {
        if(!isEnabled())return;
        if(fingers>=3 && (kind.equals("tap") || kind.equals("hold"))) {openMenu();return;}
        if(menu || keyboard || confirmingExit) {menuGesture(fingers,kind);return;}
        if(fingers==1) {
            switch(kind) {
                case "up":command("up");break;
                case "down":command("down");break;
                case "left":command("shift_tab");break;
                case "right":command("tab");break;
                case "double":command("enter");break;
                case "tap":command("silence");break;
            }
        } else if(fingers==2) {
            switch(kind) {
                case "tap":command("focus");break;
                case "double":command("space");break;
                case "up":command("window");break;
                case "down":command("read_all");break;
                case "left":command("escape");break;
                case "right":command("alt_tab");break;
            }
        } else if(fingers==3) {
            if(kind.equals("up"))command("home");
            else if(kind.equals("down"))command("end");
            else if(kind.equals("left"))command("backspace");
            else if(kind.equals("right"))openKeyboard();
        }
    }
    private void menuGesture(int fingers,String kind) {
        if(fingers==2 && kind.equals("left")) {leaveMenu();return;}
        if(confirmingExit) {
            if(fingers==1 && kind.equals("double")) {activity.exitFromNvdaTouch();return;}
            announce(activity.getString(R.string.nvda_exit_confirm));return;
        }
        if(keyboard) {
            if(fingers==1 && (kind.equals("up") || kind.equals("down"))) {
                group=Math.floorMod(group+(kind.equals("down")?1:-1),alphabets.length);character=0;speakCharacter();
            } else if(fingers==1 && (kind.equals("right") || kind.equals("left"))) {
                character=Math.floorMod(character+(kind.equals("right")?1:-1),alphabets[group].length());speakCharacter();
            } else if(fingers==1 && kind.equals("double")) {
                command("text",String.valueOf(alphabets[group].charAt(character)));
            } else if(fingers==2 && kind.equals("tap"))command("space");
            else if(fingers==2 && kind.equals("right"))command("backspace");
            else if(fingers==2 && kind.equals("double"))command("enter");
            return;
        }
        if(fingers==1 && (kind.equals("right") || kind.equals("down") || kind.equals("left") || kind.equals("up"))) {
            selection=Math.floorMod(selection+((kind.equals("right") || kind.equals("down"))?1:-1),actions.length);
            surface.invalidate();announce(item());
        } else if(fingers==1 && kind.equals("double")) {
            String action=actions[selection];
            switch(action) {
                case "close":leaveMenu();break;
                case "keyboard":openKeyboard();break;
                case "help":announce(activity.getString(R.string.nvda_touch_help));break;
                case "restart":nvda.restart();rescue(activity.getString(R.string.nvda_starting));break;
                case "disable":
                    // This is spoken before hiding the only touch surface.
                    rescue(activity.getString(R.string.nvda_touch_disabled));
                    activity.getPreferences().edit().putBoolean(NvdaController.TOUCH_MODE,false).apply();
                    main.postDelayed(activity::updateNvdaTouchMode,1800);break;
                case "exit":menu=false;confirmingExit=true;surface.invalidate();announce(activity.getString(R.string.nvda_exit_confirm));break;
                default:menu=false;surface.invalidate();command(action);break;
            }
        } else if(fingers==1 && kind.equals("tap"))announce(item());
    }
    private void openKeyboard() {
        menu=false;keyboard=true;group=character=0;surface.invalidate();
        announce(activity.getString(R.string.nvda_keyboard_help)+". "+activity.getString(groupNames[group])+". a");
    }
    private void speakCharacter() {
        surface.invalidate();announce(activity.getString(groupNames[group])+". "+alphabets[group].charAt(character));
    }
    private final class Surface extends View {
        private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        Surface() {super(activity);setKeepScreenOn(true);}
        @Override public boolean onTouchEvent(MotionEvent event) {
            if(!NvdaTouchController.this.isEnabled() || !event.isFromSource(InputDevice.SOURCE_TOUCHSCREEN))return false;
            return gestures.onTouch(event);
        }
        @Override protected void onDraw(Canvas canvas) {
            if(!menu && !keyboard && !confirmingExit)return;
            canvas.drawColor(0xED101820);paint.setColor(Color.WHITE);
            paint.setTextSize(20*getResources().getDisplayMetrics().scaledDensity);
            String title=confirmingExit?activity.getString(R.string.nvda_exit_environment):keyboard?
                activity.getString(groupNames[group])+": "+alphabets[group].charAt(character):activity.getString(labels[selection]);
            canvas.drawText(title,24,getHeight()/2f,paint);
        }
    }
    @Override public void close() {
        if(closed)return;
        closed=true;voiceGeneration++;gestures.cancel();main.removeCallbacksAndMessages(null);
        rescueVoice.stop();rescueVoice.shutdown();surface.setVisibility(View.GONE);
    }
}
