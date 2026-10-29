package com.winlator.accessibility;

import android.app.Activity;
import android.content.Context;
import android.view.View;
import android.widget.FrameLayout;
import java.util.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class NvdaWindowTouchInterceptorTest {
    private static class Endpoint extends FrameLayout {
        final List<Boolean> received=new ArrayList<>();
        Endpoint(Context c) {super(c);}
        @Override public void requestDisallowInterceptTouchEvent(boolean value) {received.add(value);super.requestDisallowInterceptTouchEvent(value);}
    }
    private static class BlockingChild extends FrameLayout {
        BlockingChild(Context c) {super(c);}
        @Override public void requestDisallowInterceptTouchEvent(boolean value) { }
    }
    @Test public void decorRequestBypassesAnIntermediateChildWhichSwallowsPropagation() {
        Context c=RuntimeEnvironment.getApplication();Endpoint windowParent=new Endpoint(c);
        FrameLayout decor=new FrameLayout(c),content=new FrameLayout(c);BlockingChild child=new BlockingChild(c);
        windowParent.addView(decor);decor.addView(child);child.addView(content);
        content.requestDisallowInterceptTouchEvent(true);assertTrue(windowParent.received.isEmpty());
        NvdaWindowTouchInterceptor interceptor=new NvdaWindowTouchInterceptor((View)decor);
        interceptor.request(true);assertEquals(List.of(true),windowParent.received);
        interceptor.request(false);assertEquals(List.of(true,false),windowParent.received);
    }
    @Test public void actualActivityWindowAcceptsAndReleasesTheRequest() {
        Activity activity=Robolectric.buildActivity(Activity.class).setup().get();
        NvdaWindowTouchInterceptor interceptor=new NvdaWindowTouchInterceptor(activity.getWindow());
        interceptor.request(true);assertTrue(interceptor.diagnostics().contains("đã gọi được=true"));
        interceptor.request(false);assertTrue(interceptor.diagnostics().contains("yêu cầu cuối=false"));
        activity.finish();
    }
    @Test public void missingWindowDecorIsReportedWithoutCrashingInput() {
        NvdaWindowTouchInterceptor interceptor=new NvdaWindowTouchInterceptor((View)null);interceptor.request(true);
        assertTrue(interceptor.diagnostics().contains("đã gọi được=false"));
    }
}
