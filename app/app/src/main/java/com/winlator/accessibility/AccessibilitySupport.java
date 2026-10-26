package com.winlator.accessibility;

import android.app.Activity;
import android.content.Context;
import android.content.ContextWrapper;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.view.accessibility.AccessibilityManager;
import android.view.accessibility.AccessibilityNodeInfo;

/** Shared semantics for adjustable controls and modal focus restoration. */
public final class AccessibilitySupport {
    private AccessibilitySupport() {}

    public static void range(AccessibilityNodeInfo info, float min, float max, float value, boolean enabled) {
        info.setClassName(android.widget.SeekBar.class.getName());
        if (max <= min) return;
        info.setRangeInfo(AccessibilityNodeInfo.RangeInfo.obtain(
                AccessibilityNodeInfo.RangeInfo.RANGE_TYPE_FLOAT, min, max, value));
        info.setScrollable(enabled);
        if (enabled) {
            info.addAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_SET_PROGRESS);
            if (value < max) info.addAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD);
            if (value > min) info.addAction(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD);
        }
    }

    public static Float requestedValue(int action, Bundle args, float min, float max, float value, float step) {
        float next;
        if (action == AccessibilityNodeInfo.ACTION_SCROLL_FORWARD) next = value + step;
        else if (action == AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD) next = value - step;
        else if (action == AccessibilityNodeInfo.AccessibilityAction.ACTION_SET_PROGRESS.getId()) {
            if (args == null || !args.containsKey(AccessibilityNodeInfo.ACTION_ARGUMENT_PROGRESS_VALUE)) return null;
            next = args.getFloat(AccessibilityNodeInfo.ACTION_ARGUMENT_PROGRESS_VALUE);
        }
        else return null;
        if (Float.isNaN(next) || Float.isInfinite(next) || max <= min) return null;
        return Math.max(min, Math.min(max, next));
    }

    private static boolean touchExploration(Context context) {
        AccessibilityManager manager = (AccessibilityManager)context.getSystemService(Context.ACCESSIBILITY_SERVICE);
        return manager != null && manager.isEnabled() && manager.isTouchExplorationEnabled();
    }

    public static View captureFocus(Context context) {
        while (context instanceof ContextWrapper && !(context instanceof Activity)) {
            Context next = ((ContextWrapper)context).getBaseContext();
            if (next == context) break;
            context = next;
        }
        if (!(context instanceof Activity) || !touchExploration(context)) return null;
        Activity activity = (Activity)context;
        View found = focused(activity.getWindow().getDecorView());
        return found != null ? found : activity.getCurrentFocus();
    }

    private static View focused(View view) {
        if (view.isAccessibilityFocused()) return view;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup)view;
            for (int i = 0; i < group.getChildCount(); i++) {
                View found = focused(group.getChildAt(i));
                if (found != null) return found;
            }
        }
        return null;
    }

    public static void restoreFocus(View view) {
        if (view == null || !touchExploration(view.getContext())) return;
        view.postDelayed(() -> {
            if (view.isAttachedToWindow() && view.isShown() && view.hasWindowFocus())
                view.performAccessibilityAction(AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS, null);
        }, 100);
    }

    public static void focusDialog(View content) {
        if (!touchExploration(content.getContext())) return;
        content.post(() -> {
            View first = firstControl(content);
            if (first != null) first.performAccessibilityAction(AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS, null);
        });
    }

    private static View firstControl(View view) {
        if (!view.isShown() || !view.isEnabled() || view.getImportantForAccessibility() == View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS) return null;
        if (view.getImportantForAccessibility() != View.IMPORTANT_FOR_ACCESSIBILITY_NO && (view.isFocusable() || view.isClickable())) return view;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup)view;
            for (int i = 0; i < group.getChildCount(); i++) {
                View found = firstControl(group.getChildAt(i));
                if (found != null) return found;
            }
        }
        return null;
    }
}
