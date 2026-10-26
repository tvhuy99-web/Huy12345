package com.winlator.widget;

import android.content.Context;
import android.util.AttributeSet;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import androidx.appcompat.widget.AppCompatSpinner;

/** Preserve both a compact field label and its current selection for screen readers. */
public class LabeledSpinner extends AppCompatSpinner {
    public LabeledSpinner(Context context) { this(context, null); }
    public LabeledSpinner(Context context, AttributeSet attrs) { super(context, attrs); }

    private CharSequence description() {
        CharSequence label = getContentDescription();
        Object selected = getSelectedItem();
        return selected == null ? label : (label == null ? selected.toString() : label + ", " + selected);
    }

    @Override public void onInitializeAccessibilityNodeInfo(AccessibilityNodeInfo info) {
        super.onInitializeAccessibilityNodeInfo(info);
        info.setClassName(android.widget.Spinner.class.getName());
        info.setContentDescription(description());
    }

    @Override public void onInitializeAccessibilityEvent(AccessibilityEvent event) {
        super.onInitializeAccessibilityEvent(event);
        event.setContentDescription(description());
    }
}
