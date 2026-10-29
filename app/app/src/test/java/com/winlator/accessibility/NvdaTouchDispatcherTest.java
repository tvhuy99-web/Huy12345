package com.winlator.accessibility;

import android.os.Handler;
import android.os.Looper;
import android.view.InputDevice;
import android.view.MotionEvent;
import java.time.Duration;
import java.util.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.LooperMode;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28) @LooperMode(LooperMode.Mode.PAUSED)
public class NvdaTouchDispatcherTest {
    private final List<String> gestures=new ArrayList<>();
    private final List<Boolean> locks=new ArrayList<>();
    private final NvdaTouchDispatcher dispatcher=new NvdaTouchDispatcher(
        new NvdaGestureRecognizer(new Handler(Looper.getMainLooper()),1,(count,kind)->gestures.add(count+":"+kind)),locks::add);
    private boolean event(long time,int action,boolean available,int source,int... ids) {
        MotionEvent.PointerProperties[] props=new MotionEvent.PointerProperties[ids.length];
        MotionEvent.PointerCoords[] coords=new MotionEvent.PointerCoords[ids.length];
        for(int i=0;i<ids.length;i++) {
            props[i]=new MotionEvent.PointerProperties();props[i].id=ids[i];props[i].toolType=MotionEvent.TOOL_TYPE_FINGER;
            coords[i]=new MotionEvent.PointerCoords();coords[i].x=100+i*70;coords[i].y=100;
        }
        MotionEvent e=MotionEvent.obtain(0,time,action,ids.length,props,coords,0,0,1,1,0,0,source,0);
        try {return dispatcher.dispatch(e,available);}finally {e.recycle();}
    }
    private boolean touch(long time,int action,boolean available,int... ids) {
        return event(time,action,available,InputDevice.SOURCE_TOUCHSCREEN,ids);
    }
    private void downThree() {
        assertTrue(touch(0,MotionEvent.ACTION_DOWN,true,1));
        assertTrue(touch(60,MotionEvent.ACTION_POINTER_DOWN|(1<<8),true,1,7));
        assertTrue(touch(120,MotionEvent.ACTION_POINTER_DOWN|(2<<8),true,1,7,19));
    }
    @Test public void disabledInputAndExternalMouseFallThroughToNormalControls() {
        assertFalse(touch(0,MotionEvent.ACTION_DOWN,false,1));
        assertFalse(event(0,MotionEvent.ACTION_DOWN,true,InputDevice.SOURCE_MOUSE,1));
        assertTrue(gestures.isEmpty());assertTrue(locks.isEmpty());
    }
    @Test public void wholeSequenceIsConsumedAndInterceptionIsUnlockedAtTheEnd() {
        downThree();
        assertTrue(touch(200,MotionEvent.ACTION_POINTER_UP|(1<<8),true,1,7,19));
        assertTrue(touch(240,MotionEvent.ACTION_POINTER_UP,true,1,19));
        assertTrue(touch(280,MotionEvent.ACTION_UP,true,19));
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(361));
        assertEquals(List.of("3:tap"),gestures);assertEquals(List.of(true,true,true,false),locks);
    }
    @Test public void foregroundSystemCancelRecoversOnlyTheOwnedContactSession() {
        downThree();assertTrue(touch(220,MotionEvent.ACTION_CANCEL,true,1,7,19));
        assertFalse(touch(260,MotionEvent.ACTION_UP,true,1));
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(361));
        assertEquals(List.of("3:tap"),gestures);assertFalse(locks.get(locks.size()-1));
    }
    @Test public void unavailableWindowDiscardsTheSequenceWithoutRecoveringAnAction() {
        downThree();assertTrue(touch(220,MotionEvent.ACTION_CANCEL,false,1,7,19));
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));assertTrue(gestures.isEmpty());
        assertFalse(locks.get(locks.size()-1));
    }
    @Test public void focusOrModeCancellationDiscardsPendingMultiTapActions() {
        downThree();touch(200,MotionEvent.ACTION_CANCEL,true,1,7,19);
        dispatcher.cancel();shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));
        assertTrue(gestures.isEmpty());assertFalse(touch(300,MotionEvent.ACTION_UP,true,1));
    }
    @Test public void missingInitialDownNeverCapturesAChildOrAnotherWindowsGesture() {
        assertFalse(touch(60,MotionEvent.ACTION_POINTER_DOWN|(2<<8),true,1,7,19));
        assertFalse(touch(200,MotionEvent.ACTION_CANCEL,true,1,7,19));
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));
        assertTrue(gestures.isEmpty());assertTrue(locks.isEmpty());
    }
}
