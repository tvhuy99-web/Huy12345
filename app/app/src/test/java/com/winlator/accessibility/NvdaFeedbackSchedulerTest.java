package com.winlator.accessibility;

import android.os.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.*;
import java.time.Duration;
import java.util.*;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28) @LooperMode(LooperMode.Mode.PAUSED)
public class NvdaFeedbackSchedulerTest {
    @Test public void consecutiveKeysCoalesceIntoTheMostRecentObservation() {
        List<String> ids=new ArrayList<>();NvdaFeedbackScheduler queue=new NvdaFeedbackScheduler(new Handler(Looper.getMainLooper()),(id,done)->{ids.add(id);done.run();});
        queue.request("first");queue.request("second");queue.request("last");
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(200));assertEquals(List.of("last"),ids);
    }
    @Test public void busyFeedbackKeepsOneLatestRequestWithoutBlockingKeyCallers() {
        List<String> ids=new ArrayList<>();List<Runnable> callbacks=new ArrayList<>();
        NvdaFeedbackScheduler queue=new NvdaFeedbackScheduler(new Handler(Looper.getMainLooper()),(id,done)->{ids.add(id);callbacks.add(done);});
        queue.request("one");shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(200));
        queue.request("two");queue.request("three");shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));
        assertEquals(List.of("one"),ids);callbacks.get(0).run();shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(100));
        assertEquals(List.of("one","three"),ids);
    }
    @Test public void pauseDiscardsPendingAndLateFeedbackCallbacks() {
        List<String> ids=new ArrayList<>();List<Runnable> callbacks=new ArrayList<>();
        NvdaFeedbackScheduler queue=new NvdaFeedbackScheduler(new Handler(Looper.getMainLooper()),(id,done)->{ids.add(id);callbacks.add(done);});
        queue.request("beforePause");shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(200));
        queue.request("stale");queue.cancel();callbacks.get(0).run();shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));
        assertEquals(List.of("beforePause"),ids);
    }
}
