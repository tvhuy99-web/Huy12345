package com.winlator.accessibility;

import android.view.InputDevice;
import android.view.MotionEvent;
import java.util.function.Consumer;

/** Owns a touchscreen sequence before DrawerLayout or a child view can split/cancel it. */
public final class NvdaTouchDispatcher {
    private final NvdaGestureRecognizer recognizer;
    private final Consumer<Boolean> intercept;
    private boolean capturing;

    public NvdaTouchDispatcher(NvdaGestureRecognizer recognizer,Consumer<Boolean> intercept) {
        this.recognizer=recognizer;this.intercept=intercept;
    }
    public boolean dispatch(MotionEvent event,boolean available) {
        int action=event.getActionMasked();
        if(action==MotionEvent.ACTION_DOWN) {
            if(capturing)cancel();
            capturing=available&&event.isFromSource(InputDevice.SOURCE_TOUCHSCREEN);
            if(capturing)intercept.accept(true);
        }
        if(!capturing)return false;
        if(!available) {cancel();return true;}
        if(action==MotionEvent.ACTION_POINTER_DOWN)intercept.accept(true);
        try {recognizer.onTouch(event,true);}
        finally {
            if(action==MotionEvent.ACTION_UP||action==MotionEvent.ACTION_CANCEL) {
                capturing=false;intercept.accept(false);
            }
        }
        return true;
    }
    public void cancel() {capturing=false;recognizer.cancel();intercept.accept(false);}
}
