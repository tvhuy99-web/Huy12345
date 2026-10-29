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
        MotionEvent e=MotionEvent.obtain(0,time,action,ids.length,props,coords,0,0,1,1,0,0,InputDevice.SOURCE_TOUCHSCREEN,eventFlags);
        detector.onTouch(e);e.recycle();
    }
    private void tap(long start) {
        event(start,MotionEvent.ACTION_DOWN,new int[]{7},100,100);
        event(start+40,MotionEvent.ACTION_UP,new int[]{7},100,100);
    }
    @Test public void doubleTapOnlyActivatesOnceAndNeverSendsSingleTap() {
        tap(0);tap(160);shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(370));
        assertEquals(List.of("1:double"),commands);
    }
    @Test public void singleTapWaitsForDoubleTapWindow() {
        tap(0);assertTrue(commands.isEmpty());shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(361));
        assertEquals(List.of("1:tap"),commands);
    }
    @Test public void verticalSwipeIsOneArrowWithoutTapOrMouseClick() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{7},100,100);
        event(90,MotionEvent.ACTION_MOVE,new int[]{7},103,180);
        event(120,MotionEvent.ACTION_UP,new int[]{7},103,210);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(370));
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
        tap(1200);detector.cancel();shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(370));assertTrue(commands.isEmpty());
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
        assertTrue(commands.isEmpty());shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(361));
        assertEquals(List.of("3:tap"),commands);
    }
    @Test public void diagonalMotionIsNotMistakenForTabOrEnter() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{7},100,100);
        event(100,MotionEvent.ACTION_UP,new int[]{7},200,200);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(370));assertTrue(commands.isEmpty());
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
            assertTrue(commands.isEmpty());shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(361));
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
    @Test public void holdingThreeFingersNeverOpensAMenuBeforeMovement() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(10,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(801));
        assertTrue(commands.isEmpty());detector.cancel();
    }
    private int eventFlags;
    private void chord(int count,long start,float[] displacement,boolean cancel) {
        int[] ids=new int[count];float[] xy=new float[count*2];
        for(int i=0;i<count;i++) {
            ids[i]=10+i;xy[i*2]=200+i*70;xy[i*2+1]=200;
            event(start+i*60,i==0?MotionEvent.ACTION_DOWN:MotionEvent.ACTION_POINTER_DOWN|(i<<8),
                java.util.Arrays.copyOf(ids,i+1),java.util.Arrays.copyOf(xy,(i+1)*2));
            // The first finger starts moving while the rest of the hand is still joining.
            xy[0]+=displacement[0]*.22f;xy[1]+=displacement[1]*.22f;
            event(start+i*60+15,MotionEvent.ACTION_MOVE,java.util.Arrays.copyOf(ids,i+1),java.util.Arrays.copyOf(xy,(i+1)*2));
        }
        for(int i=0;i<count;i++) {xy[i*2]+=displacement[0];xy[i*2+1]+=displacement[1];}
        event(start+300,MotionEvent.ACTION_MOVE,ids,xy);
        if(cancel) {event(start+330,MotionEvent.ACTION_CANCEL,ids,xy);}
        else for(int n=count;n>=1;n--)event(start+330+(count-n)*35,n==1?MotionEvent.ACTION_UP:MotionEvent.ACTION_POINTER_UP|((n-1)<<8),
            java.util.Arrays.copyOf(ids,n),java.util.Arrays.copyOf(xy,n*2));
    }
    @Test public void threeAndFourFingerSwipesAllowMovementDuringTheJoin() {
        for(int count=3;count<=4;count++) {
            detector.cancel();commands.clear();chord(count,0,new float[]{0,90},false);
            assertEquals(List.of(count+":down"),commands);
        }
    }
    @Test public void handSwipeUsesAgreementInsteadOfRequiringEqualFingerTravel() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(50,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(100,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        event(200,MotionEvent.ACTION_POINTER_UP|(2<<8),new int[]{1,2,3},100,200,200,190,300,110);
        event(230,MotionEvent.ACTION_POINTER_UP|(1<<8),new int[]{1,2},100,200,200,190);
        event(260,MotionEvent.ACTION_UP,new int[]{1},100,200);
        assertEquals(List.of("3:down"),commands);
    }
    @Test public void multiFingerTapAllowsNaturalStaggeredPressAndRelease() {
        for(int count=3;count<=4;count++) {
            detector.cancel();commands.clear();chord(count,0,new float[]{0,0},false);
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(361));
            assertEquals(List.of(count+":tap"),commands);
        }
    }
    @Test public void lateAdditionalFingerCannotChangeAnExistingGesture() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(330,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(350,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        event(400,MotionEvent.ACTION_CANCEL,new int[]{1,2,3},100,100,200,100,300,100);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));assertTrue(commands.isEmpty());
    }
    @Test public void cancelledSwipesCannotExecuteEvenWithAPreviouslyKnownDirection() {
        String[] names={"up","down","left","right"};float[][] delta={{0,-100},{0,100},{-100,0},{100,0}};
        for(int count=3;count<=4;count++)for(int i=0;i<4;i++) {
            detector.cancel();commands.clear();chord(count,0,delta[i],true);
            event(400,MotionEvent.ACTION_UP,new int[]{10},200,200);
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));
            assertTrue(commands.isEmpty());
        }
    }
    @Test public void cancelledContactsNeverInventSingleDoubleOrTripleTaps() {
        for(int count=3;count<=4;count++)for(int number=1;number<=3;number++) {
            detector.cancel();commands.clear();
            for(int i=0;i<number;i++)chord(count,i*500,new float[]{0,0},true);
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(361));
            assertTrue(commands.isEmpty());
        }
    }
    @Test public void ordinaryViewCancelDoesNotRecoverThreeFingerAction() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(10,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        event(120,MotionEvent.ACTION_CANCEL,new int[]{1,2,3},100,200,200,200,300,200);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));assertTrue(commands.isEmpty());
    }
    @Test public void oneAndTwoFingerCancelNeverBecomeKeys() {

        for(int count=1;count<=2;count++) {
            detector.cancel();commands.clear();
            event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
            if(count==2)event(20,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
            event(150,MotionEvent.ACTION_CANCEL,count==1?new int[]{1}:new int[]{1,2},count==1?new float[]{200,100}:new float[]{200,100,300,100});
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));assertTrue(commands.isEmpty());
        }
    }
    @Test public void cancelCannotBorrowUnknownOrPreviouslyReleasedPointerIds() {

        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(40,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        event(100,MotionEvent.ACTION_CANCEL,new int[]{1,2,9},100,200,200,200,300,200);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));assertTrue(commands.isEmpty());
        event(1000,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(1020,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(1040,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        event(1100,MotionEvent.ACTION_POINTER_UP|(2<<8),new int[]{1,2,3},100,200,200,200,300,200);
        event(1120,MotionEvent.ACTION_CANCEL,new int[]{1,2},100,200,200,200);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));assertTrue(commands.isEmpty());
    }
    @Test public void longOrIncoherentSystemCancelIsDiscarded() {

        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(10,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        event(150,MotionEvent.ACTION_CANCEL,new int[]{1,2,3},0,100,200,100,400,100);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));assertTrue(commands.isEmpty());
        event(1000,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(1010,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(1020,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        event(2300,MotionEvent.ACTION_CANCEL,new int[]{1,2,3},100,200,200,200,300,200);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));assertTrue(commands.isEmpty());
    }
    @Test public void partiallyReleasedChordCannotTriggerAnActionBeforeTheLastUp() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(10,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        event(200,MotionEvent.ACTION_POINTER_UP|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(801));assertTrue(commands.isEmpty());detector.cancel();
    }
    @Test public void addingAnotherFingerAfterAReleaseDoesNotIncreaseTheChordCount() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(10,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(20,MotionEvent.ACTION_POINTER_UP|(1<<8),new int[]{1,2},100,100,200,100);
        event(30,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,3},100,100,300,100);
        event(40,MotionEvent.ACTION_POINTER_UP|(1<<8),new int[]{1,3},100,100,300,100);
        event(50,MotionEvent.ACTION_UP,new int[]{1},100,100);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));assertTrue(commands.isEmpty());
    }
    @Test public void prematureCancelAtTheThirdFingerCannotBecomeAFourFingerTapOrMenu() {

        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(40,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        event(45,MotionEvent.ACTION_CANCEL,new int[]{1,2,3},100,100,200,100,300,100);
        // The app cannot infer an unseen fourth contact or direction from a cancelled session.
        event(60,MotionEvent.ACTION_POINTER_DOWN|(3<<8),new int[]{1,2,3,4},100,100,200,100,300,100,400,100);
        event(100,MotionEvent.ACTION_MOVE,new int[]{1,2,3,4},100,200,200,200,300,200,400,200);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2));
        assertTrue(commands.isEmpty());
        assertTrue(detector.diagnostics().contains("cuối=CANCEL"));
        assertTrue(detector.diagnostics().contains("MOVE3+=0"));
    }
    @Test public void cancelCoordinatesCannotInventAMovementWhichWasNeverDelivered() {

        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(40,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        event(100,MotionEvent.ACTION_CANCEL,new int[]{1,2,3},100,0,200,0,300,0);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2));
        assertTrue(commands.isEmpty());assertTrue(detector.diagnostics().contains("dy=0dp"));
    }
    @Test public void aFrozenCancelIsDiscardedAndKeepsPriorMovementOnlyForDiagnostics() {

        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,200);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,200,200,200);
        event(40,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,200,200,200,300,200);
        event(100,MotionEvent.ACTION_MOVE,new int[]{1,2,3},100,100,200,100,300,100);
        event(120,MotionEvent.ACTION_CANCEL,new int[]{1,2,3},100,200,200,200,300,200);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2));
        assertTrue(commands.isEmpty());
        assertTrue(detector.diagnostics().contains("dy=-100dp"));
    }
    @Test public void aPendingRealTapIsNotFlushedAsAMenuWhenTheNextGestureIsCancelled() {
        multiTap(3,0);
        event(200,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(220,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(240,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        event(260,MotionEvent.ACTION_CANCEL,new int[]{1,2,3},100,100,200,100,300,100);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2));assertTrue(commands.isEmpty());
    }
    @Test public void holdingFourFingersThenSwipingDoesNotEmitAnAutomaticMenu() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,200);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,200,200,200);
        event(40,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,200,200,200,300,200);
        event(60,MotionEvent.ACTION_POINTER_DOWN|(3<<8),new int[]{1,2,3,4},100,200,200,200,300,200,400,200);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(900));assertTrue(commands.isEmpty());
        event(920,MotionEvent.ACTION_MOVE,new int[]{1,2,3,4},100,100,200,100,300,100,400,100);
        event(940,MotionEvent.ACTION_POINTER_UP|(3<<8),new int[]{1,2,3,4},100,100,200,100,300,100,400,100);
        event(960,MotionEvent.ACTION_POINTER_UP|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        event(980,MotionEvent.ACTION_POINTER_UP|(1<<8),new int[]{1,2},100,100,200,100);
        event(1000,MotionEvent.ACTION_UP,new int[]{1},100,100);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(400));assertEquals(List.of("4:up"),commands);
    }
    @Test public void multiTapDiagnosticsSurviveSingleFingerMenuNavigationAndStayBounded() {

        for(int i=0;i<12;i++)chord(3,i*500,new float[]{0,0},true);
        for(int i=0;i<20;i++)tap(10000+i*1000);
        String report=detector.diagnostics();
        assertEquals(8,report.split("cuối=CANCEL",-1).length-1);
        assertTrue(report.contains("Ngón tối đa đã nhận: 3"));
        assertTrue(report.length()<2500);assertFalse(report.contains("10000"));
        detector.cancel();assertTrue(detector.diagnostics().contains("cuối=CANCEL"));
    }
    @Test public void palmRejectedPointerCannotCompleteAThreeFingerTap() {
        event(0,MotionEvent.ACTION_DOWN,new int[]{1},100,100);
        event(20,MotionEvent.ACTION_POINTER_DOWN|(1<<8),new int[]{1,2},100,100,200,100);
        event(40,MotionEvent.ACTION_POINTER_DOWN|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        eventFlags=MotionEvent.FLAG_CANCELED;
        event(60,MotionEvent.ACTION_POINTER_UP|(2<<8),new int[]{1,2,3},100,100,200,100,300,100);
        eventFlags=0;
        event(80,MotionEvent.ACTION_POINTER_UP|(1<<8),new int[]{1,2},100,100,200,100);
        event(100,MotionEvent.ACTION_UP,new int[]{1},100,100);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2));
        assertTrue(commands.isEmpty());assertTrue(detector.diagnostics().contains("POINTER_CANCEL"));
    }
}
