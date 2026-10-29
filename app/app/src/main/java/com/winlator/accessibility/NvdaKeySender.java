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
    public boolean send(NvdaShortcut shortcut,Runnable delivered) {
        if(waiting.size()>=16)return false;
        waiting.add(()->{
            int request=generation;
            try {
                for(String modifier:shortcut.modifiers)press(key(modifier));
                press(key(shortcut.key));
                release=()->{releaseOwned();busy=false;release=null;if(request==generation)delivered.run();next();};
                handler.postDelayed(release,40);
            }catch(Exception e) {releaseOwned();busy=false;next();}
        });next();return true;
    }
    private void press(XKeycode key) {if(!sink.pressed(key)) {owned.add(key);sink.press(key);}}
    private void next() {if(!busy && !waiting.isEmpty()) {busy=true;waiting.remove().run();}}
    private void releaseOwned() {for(int i=owned.size()-1;i>=0;i--)try{sink.release(owned.get(i));}catch(Exception ignored){}owned.clear();}
    public void cancel() {generation++;waiting.clear();if(release!=null)handler.removeCallbacks(release);release=null;releaseOwned();busy=false;}
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
