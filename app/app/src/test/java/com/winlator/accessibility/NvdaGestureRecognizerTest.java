package com.winlator.accessibility;

import android.os.Handler;
import android.os.Looper;
import android.view.InputDevice;
import android.view.MotionEvent;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.LooperMode;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28) @LooperMode(LooperMode.Mode.PAUSED)
public class NvdaGestureRecognizerTest {
    private final List<String> commands=new ArrayList<>();
    private final NvdaGestureRecognizer detector=new NvdaGestureRecognizer(new Handler(Looper.getMainLooper()),1,
        (count,kind)->commands.add(count+":"+kind));
    private void event(long time,int action,int[] ids,float... xy) {
        MotionEvent.PointerProperties[] props=new MotionEvent.PointerProperties[ids.length];
        MotionEvent.PointerCoords[] coords=new MotionEvent.PointerCoords[ids.length];
        for(int i=0;i<ids.length;i++) {
            props[i]=new MotionEvent.PointerProperties();props[i].id=ids[i];props[i].toolType=MotionEvent.TOOL_TYPE_FINGER;
            coords[i]=new MotionEvent.PointerCoords();coords[i].x=xy[i*2];coords[i].y=xy[i*2+1];
        }
        MotionEvent e=MotionEvent.obtain(0,time,action,ids.length,props,coords,0,0,1,1,0,0,InputDevice.SOURCE_TOUCHSCREEN,0);
        detector.onTouch(e);e.recycle();
    }
    private void tap(long start) {
        event(start,MotionEvent.ACTION_DOWN,new int[]{7},100,100);
        event(start+40,MotionEvent.ACTION_UP,new int[]{7},100,100);
    }
    @Test public void doubleTapOnlyActivatesOnceAndNeverSendsSingleTap() {
        tap(0);tap(160);shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(350));
        assertEquals(List.of("1:double"),commands);
    }
    @Test public void singleTapWaitsForDoubleTapWindow() {
        tap(0);assertTrue(commands.isEmpty());shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(301));
        assertEquals(List.of("1:tap"),commands);
    }
    @Test public void verticalSwipeIsOneArrowWithoutTapOrMouseClick() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{7},100,100);
        event(90,MotionEvent.ACTION_MOVE,new int[]{7},103,180);
        event(120,MotionEvent.ACTION_UP,new int[]{7},103,210);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(350));
        assertEquals(List.of("1:down"),commands);
    }
    @Test public void tracksPointerIdsWhenFirstFingerLiftsBeforeSecond() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{7},100,100);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{7,19},100,100,200,100);
        event(70,MotionEvent.ACTION_MOVE,new int[]{19,7},300,100,200,100);
        event(100,MotionEvent.ACTION_POINTER_UP|(1<<8),new int[]{19,7},310,100,210,100);
        event(120,MotionEvent.ACTION_UP,new int[]{19},320,100);
        assertEquals(List.of("2:right"),commands);
    }
    @Test public void cancelAndModeChangeDiscardPendingActions() {
        tap(0);event(100,MotionEvent.ACTION_CANCEL,new int[]{7},100,100);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(1000));assertTrue(commands.isEmpty());
        tap(1200);detector.cancel();shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(350));assertTrue(commands.isEmpty());
    }
    @Test public void pinchNeverBecomesAnArrow() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{7},100,100);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{7,19},100,100,200,100);
        event(100,MotionEvent.ACTION_POINTER_UP|(1<<8),new int[]{7,19},0,100,300,100);
        event(120,MotionEvent.ACTION_UP,new int[]{7},0,100);
        assertTrue(commands.isEmpty());
    }
    @Test public void threeFingerTapOpensRescueWithoutWaitingForDoubleTap() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{7},100,100);
        event(10,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{7,19},100,100,200,100);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{7,19,23},100,100,200,100,300,100);
        event(60,MotionEvent.ACTION_POINTER_UP|(2<<8),new int[]{7,19,23},100,100,200,100,300,100);
        event(70,MotionEvent.ACTION_POINTER_UP|(1<<8),new int[]{7,19},100,100,200,100);
        event(80,MotionEvent.ACTION_UP,new int[]{7},100,100);
        assertEquals(List.of("3:tap"),commands);
    }
    @Test public void diagonalMotionIsNotMistakenForTabOrEnter() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{7},100,100);
        event(100,MotionEvent.ACTION_UP,new int[]{7},200,200);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(350));assertTrue(commands.isEmpty());
    }
}
