package com.winlator.accessibility;

import android.view.View;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import com.winlator.R;

/** Keep Android role and event semantics in sync with the current guest state. */
public final class GuestControlAccessibilityDelegate extends View.AccessibilityDelegate {
    @Override public void onInitializeAccessibilityNodeInfo(View host, AccessibilityNodeInfo info) {
        super.onInitializeAccessibilityNodeInfo(host, info);
        GuestSnapshot.Node node = (GuestSnapshot.Node)host.getTag();
        if (node == null) return;
        if (node.role == 44 || node.role == 45) {
            info.setClassName(node.role == 44 ? android.widget.CheckBox.class.getName() : android.widget.RadioButton.class.getName());
            info.setCheckable(true); info.setChecked(node.checked());
        } else if (node.click || node.edit) info.setClassName(android.widget.Button.class.getName());
        info.setSelected(node.selected());
        info.addAction(new AccessibilityNodeInfo.AccessibilityAction(
                AccessibilityNodeInfo.ACTION_LONG_CLICK, host.getContext().getString(R.string.guest_focus)));
    }
    @Override public void onInitializeAccessibilityEvent(View host, AccessibilityEvent event) {
        super.onInitializeAccessibilityEvent(host, event);
        GuestSnapshot.Node node = (GuestSnapshot.Node)host.getTag();
        if (node == null) return;
        if (node.role == 44 || node.role == 45) {
            event.setClassName(node.role == 44 ? android.widget.CheckBox.class.getName() : android.widget.RadioButton.class.getName());
            event.setChecked(node.checked());
        }
    }
}
