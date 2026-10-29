package com.winlator.accessibility;

import android.os.Handler;
import com.winlator.xserver.XKeycode;
import java.util.*;

/** Sends real X keyboard events, with ordered chords and owned-key release on every exit. */
public final class NvdaKeySender {
    public interface Sink {boolean pressed(XKeycode key);void press(XKeycode key);void release(XKeycode key);}
    private final Handler handler;private final Sink sink;
    private final ArrayDeque<Runnable> waiting=new ArrayDeque<>();
    private final List<XKeycode> owned=new ArrayList<>();
    private Runnable release;private boolean busy;private int generation;
    public NvdaKeySender(Handler handler,Sink sink) {this.handler=handler;this.sink=sink;}
    public boolean send(NvdaShortcut shortcut,Runnable delivered) {return send(shortcut,delivered,()->{});}
    public boolean send(NvdaShortcut shortcut,Runnable delivered,Runnable failed) {
        if(waiting.size()>=16) {NvdaDiagnosticLog.record("keys.rejected","Queue full");return false;}
        NvdaDiagnosticLog.record("keys.queued",NvdaDiagnosticLog.shortcut(shortcut.canonical()));
        waiting.add(()->{
            int request=generation;
            try {
                for(String modifier:shortcut.modifiers)press(key(modifier));
                press(key(shortcut.key));
                release=()->{
                    boolean released=releaseOwned();busy=false;release=null;
                    NvdaDiagnosticLog.record(released?"keys.delivered":"keys.failed",NvdaDiagnosticLog.shortcut(shortcut.canonical()));
                    if(request==generation) {if(released)delivered.run();else failed.run();}next();
                };
                handler.postDelayed(release,40);
            }catch(Exception e) {NvdaDiagnosticLog.error("keys.error",e);releaseOwned();busy=false;if(request==generation)failed.run();next();}
        });next();return true;
    }
    private void press(XKeycode key) {NvdaDiagnosticLog.record("keys.press", "key="+traceKey(key));if(!sink.pressed(key)) {owned.add(key);sink.press(key);}}
    private void next() {if(!busy && !waiting.isEmpty()) {busy=true;waiting.remove().run();}}
    private boolean releaseOwned() {
        boolean success=true;
        for(int i=owned.size()-1;i>=0;i--)try {
            NvdaDiagnosticLog.record("keys.release","key="+traceKey(owned.get(i)));sink.release(owned.get(i));
        }catch(Exception e) {success=false;NvdaDiagnosticLog.error("keys.release.failed",e);}
        owned.clear();return success;
    }
    private static String traceKey(XKeycode key) {
        switch(key) {
            case KEY_CTRL_L:case KEY_CTRL_R:return "control";
            case KEY_ALT_L:case KEY_ALT_R:return "alt";
            case KEY_SHIFT_L:case KEY_SHIFT_R:return "shift";
            case KEY_SUPER_L:return "windows";
            default:return NvdaDiagnosticLog.shortcut(key.name().substring(4));
        }
    }
    public void cancel() {NvdaDiagnosticLog.record("keys.cancel","Release owned keys; queued="+waiting.size());generation++;waiting.clear();if(release!=null)handler.removeCallbacks(release);release=null;releaseOwned();busy=false;}
    public static XKeycode key(String key) {
        String name;
        switch(key) {
            case "control":name="CTRL_L";break;case "windows":name="SUPER_L";break;
            case "shift":name="SHIFT_L";break;case "alt":name="ALT_L";break;
            case "escape":name="ESC";break;case "backspace":name="BKSP";break;case "delete":name="DEL";break;
            case "pageup":name="PRIOR";break;case "pagedown":name="NEXT";break;
            case "bracketleft":name="BRACKET_LEFT";break;case "bracketright":name="BRACKET_RIGHT";break;
            default:name=key.toUpperCase(Locale.ROOT);
        }
        return XKeycode.valueOf("KEY_"+name);
    }
}
