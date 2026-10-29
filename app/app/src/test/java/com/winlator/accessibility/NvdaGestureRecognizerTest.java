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
    @Test public void threeFingerTapWaitsSoDoubleAndTripleRemainAvailable() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{7},100,100);
        event(10,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{7,19},100,100,200,100);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{7,19,23},100,100,200,100,300,100);
        event(60,MotionEvent.ACTION_POINTER_UP|(2<<8),new int[]{7,19,23},100,100,200,100,300,100);
        event(70,MotionEvent.ACTION_POINTER_UP|(1<<8),new int[]{7,19},100,100,200,100);
        event(80,MotionEvent.ACTION_UP,new int[]{7},100,100);
        assertTrue(commands.isEmpty());shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(301));
        assertEquals(List.of("3:tap"),commands);
    }
    @Test public void diagonalMotionIsNotMistakenForTabOrEnter() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{7},100,100);
        event(100,MotionEvent.ACTION_UP,new int[]{7},200,200);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(350));assertTrue(commands.isEmpty());
    }
    private void multiTap(int fingers,long start) {
        int[] ids=new int[fingers];float[] xy=new float[fingers*2];
        for(int i=0;i<fingers;i++) {ids[i]=7+i*3;xy[i*2]=100+i*60;xy[i*2+1]=100;}
        for(int count=1;count<=fingers;count++)event(start+count*10,count==1?MotionEvent.ACTION_DOWN:MotionEvent.ACTION_POINTER_DOWN|((count-1)<<8),java.util.Arrays.copyOf(ids,count),java.util.Arrays.copyOf(xy,count*2));
        for(int count=fingers;count>=1;count--)event(start+80+(fingers-count)*10,count==1?MotionEvent.ACTION_UP:MotionEvent.ACTION_POINTER_UP|((count-1)<<8),java.util.Arrays.copyOf(ids,count),java.util.Arrays.copyOf(xy,count*2));
    }
    @Test public void tripleTapsForTwoThreeFourFingersNeverEmitSingleOrDouble() {
        for(int count=2;count<=4;count++) {
            detector.cancel();commands.clear();multiTap(count,0);multiTap(count,160);multiTap(count,320);
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(400));
            assertEquals(List.of(count+":triple"),commands);
        }
    }
    @Test public void doubleTapsWithThreeAndFourFingersDoNotOpenTheMenuFirst() {
        for(int count=3;count<=4;count++) {
            detector.cancel();commands.clear();multiTap(count,0);multiTap(count,180);
            assertTrue(commands.isEmpty());shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(301));
            assertEquals(List.of(count+":double"),commands);
        }
    }
    @Test public void allTwelveTurnsAndReversalsAreOneGesture() {
        String[] names={"up","down","left","right"};float[][] vectors={{0,-100},{0,100},{-100,0},{100,0}};
        for(int a=0;a<4;a++)for(int b=0;b<4;b++)if(a!=b) {
            detector.cancel();commands.clear();float x=300,y=300;
            event(0,MotionEvent.ACTION_DOWN,new int[]{7},x,y);
            x+=vectors[a][0];y+=vectors[a][1];event(80,MotionEvent.ACTION_MOVE,new int[]{7},x,y);
            x+=vectors[b][0];y+=vectors[b][1];event(150,MotionEvent.ACTION_MOVE,new int[]{7},x,y);
            event(170,MotionEvent.ACTION_UP,new int[]{7},x,y);
            assertEquals(names[a]+" then "+names[b],List.of("1:"+names[a]+"_"+names[b]),commands);
        }
    }
    @Test public void thirdLegDoesNotBecomeAValidTwoLegGesture() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{7},300,300);
        event(80,MotionEvent.ACTION_MOVE,new int[]{7},400,300);
        event(160,MotionEvent.ACTION_MOVE,new int[]{7},400,200);
        event(240,MotionEvent.ACTION_UP,new int[]{7},500,200);
        assertTrue(commands.isEmpty());
    }
    @Test public void threeFingerHoldRemainsAnUnmappedRescue() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(10,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(801));
        assertEquals(List.of("3:hold"),commands);detector.cancel();
    }
}
