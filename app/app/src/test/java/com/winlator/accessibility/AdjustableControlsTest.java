package com.winlator.accessibility;

import android.content.Context;
import android.os.Bundle;
import android.view.ContextThemeWrapper;
import android.view.accessibility.AccessibilityNodeInfo;
import com.winlator.R;
import com.winlator.widget.NumberPicker;
import com.winlator.widget.SeekBar;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 28)
public class AdjustableControlsTest {
    private Context context() {
        return new ContextThemeWrapper(RuntimeEnvironment.getApplication(), R.style.AppThemeDark);
    }

    @Test public void sliderExposesRangeAndAdjustsWithoutTouch() {
        SeekBar bar = new SeekBar(context());
        bar.setMinValue(0); bar.setMaxValue(10); bar.setStep(2); bar.setValue(4);
        AtomicInteger calls = new AtomicInteger();
        bar.setOnValueChangeListener((v, value) -> calls.incrementAndGet());
        AccessibilityNodeInfo node = AccessibilityNodeInfo.obtain();
        bar.onInitializeAccessibilityNodeInfo(node);
        assertEquals(android.widget.SeekBar.class.getName(), node.getClassName());
        assertEquals(4, node.getRangeInfo().getCurrent(), 0.001);
        assertTrue(bar.performAccessibilityAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD, null));
        assertEquals(6, bar.getValue(), 0.001);
        assertEquals(1, calls.get());
        bar.setEnabled(false);
        assertFalse(bar.performAccessibilityAction(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD, null));
        assertEquals(6, bar.getValue(), 0.001);
    }

    @Test public void sliderSetProgressClampsAndRejectsNonFiniteValues() {
        SeekBar bar = new SeekBar(context());
        bar.setMinValue(0); bar.setMaxValue(10); bar.setStep(1); bar.setValue(3);
        Bundle args = new Bundle();
        args.putFloat(AccessibilityNodeInfo.ACTION_ARGUMENT_PROGRESS_VALUE, 99);
        int action = AccessibilityNodeInfo.AccessibilityAction.ACTION_SET_PROGRESS.getId();
        assertTrue(bar.performAccessibilityAction(action, args));
        assertEquals(10, bar.getValue(), 0.001);
        assertFalse(bar.performAccessibilityAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD, null));
        args.putFloat(AccessibilityNodeInfo.ACTION_ARGUMENT_PROGRESS_VALUE, Float.NaN);
        assertFalse(bar.performAccessibilityAction(action, args));
        assertEquals(10, bar.getValue(), 0.001);
    }

    @Test public void fractionalSliderStepsDoNotGetStuck() {
        SeekBar bar = new SeekBar(context());
        bar.setMinValue(0); bar.setMaxValue(1); bar.setStep(0.1f); bar.setValue(0.2f);
        assertTrue(bar.performAccessibilityAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD, null));
        assertEquals(0.3, bar.getValue(), 0.001);
    }

    @Test public void numberPickerSupportsClicksActionsAndBounds() {
        NumberPicker picker = new NumberPicker(context());
        picker.setMinValue(0); picker.setMaxValue(6); picker.setStep(2); picker.setValue(2);
        AtomicInteger calls = new AtomicInteger();
        picker.setOnValueChangeListener((v, value) -> calls.incrementAndGet());
        assertTrue(picker.findViewById(R.id.BTIncrement).performClick());
        assertEquals(4, picker.getValue());
        assertEquals(1, calls.get());
        assertTrue(picker.performAccessibilityAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD, null));
        assertEquals(6, picker.getValue());
        assertFalse(picker.performAccessibilityAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD, null));
        assertEquals(2, calls.get());
        picker.setEnabled(false);
        picker.findViewById(R.id.BTDecrement).performClick();
        assertFalse(picker.performAccessibilityAction(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD, null));
        assertEquals(6, picker.getValue());
    }
}
