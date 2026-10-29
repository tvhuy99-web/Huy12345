package com.winlator.accessibility;

import android.view.InputDevice;
import android.view.MotionEvent;
import java.util.function.Consumer;

/** Owns a touchscreen sequence before DrawerLayout or a child view can split/cancel it. */
public final class NvdaTouchDispatcher {
    private final NvdaGestureRecognizer recognizer;
    private final Consumer<Boolean> intercept;
    private boolean capturing;
    private int maximumFingers,firstLockFingers,lockCalls;
    private String lastMultiInterception="chưa có";

    public NvdaTouchDispatcher(NvdaGestureRecognizer recognizer,Consumer<Boolean> intercept) {
        this.recognizer=recognizer;this.intercept=intercept;
    }
    public boolean dispatch(MotionEvent event,boolean available) {
        int action=event.getActionMasked();
        if(action==MotionEvent.ACTION_DOWN) {
            if(capturing)cancel();
            capturing=available&&event.isFromSource(InputDevice.SOURCE_TOUCHSCREEN);
            maximumFingers=event.getPointerCount();firstLockFingers=lockCalls=0;
        }
        if(!capturing)return false;
        if(!available) {cancel();return true;}
        maximumFingers=Math.max(maximumFingers,event.getPointerCount());
        if(action==MotionEvent.ACTION_POINTER_DOWN&&event.getPointerCount()>=2) {
            if(firstLockFingers==0)firstLockFingers=event.getPointerCount();
            lockCalls++;intercept.accept(true);
        }
        boolean finished=action==MotionEvent.ACTION_UP||action==MotionEvent.ACTION_CANCEL;
        // Match the game's ordering: lock at the second finger, unlock before processing UP/CANCEL.
        if(finished) {
            if(maximumFingers>=3)lastMultiInterception="khóa từ "+firstLockFingers+" ngón; lượt khóa="+lockCalls
                +"; cuối="+(action==MotionEvent.ACTION_CANCEL?"CANCEL":"UP");
            intercept.accept(false);
        }
        try {recognizer.onTouch(event);}
        finally {
            if(action==MotionEvent.ACTION_UP||action==MotionEvent.ACTION_CANCEL) {
                capturing=false;
            }
        }
        return true;
    }
    public void cancel() {capturing=false;recognizer.cancel();intercept.accept(false);}
    public String diagnostics() {return "Khóa chuỗi nhiều ngón gần nhất: "+lastMultiInterception;}
}
