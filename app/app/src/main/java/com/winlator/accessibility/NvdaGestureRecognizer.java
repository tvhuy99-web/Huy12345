package com.winlator.accessibility;

import android.os.Handler;
import android.view.MotionEvent;
import java.util.HashMap;
import java.util.Map;

/** Tracks each pointer ID, including fingers lifted before ACTION_UP. Never clicks the desktop. */
public final class NvdaGestureRecognizer {
    public interface Listener { void onGesture(int fingers, String gesture); }
    private static final long TAP = 300, HOLD = 800;
    private final Handler handler;
    private final Listener listener;
    private final float distance, slop;
    private final Map<Integer, float[]> pointers = new HashMap<>();
    private long downTime, pendingTime;
    private int fingers, pendingFingers;
    private boolean invalid, moved;
    private Runnable pending, hold;

    public NvdaGestureRecognizer(Handler handler, float density, Listener listener) {
        this.handler = handler; this.listener = listener; distance = 48 * density; slop = 18 * density;
    }
    public void cancel() {
        if (pending != null) handler.removeCallbacks(pending);
        if (hold != null) handler.removeCallbacks(hold);
        pending = hold = null; pointers.clear(); fingers = 0; invalid = true;
    }
    public boolean onTouch(MotionEvent event) {
        int action = event.getActionMasked();
        if (action == MotionEvent.ACTION_CANCEL) { cancel(); return true; }
        if (action == MotionEvent.ACTION_DOWN) {
            pointers.clear(); fingers = 0; invalid = moved = false; downTime = event.getEventTime();
            hold = () -> { if (!invalid && !moved && fingers >= 3) {
                invalid = true; flushPending(); listener.onGesture(fingers, "hold");
            }};
            handler.postDelayed(hold, HOLD);
        }
        if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_POINTER_DOWN) {
            int i = event.getActionIndex();
            if (moved || event.getEventTime() - downTime > 250 || pointers.size() >= 4) invalid = true;
            pointers.put(event.getPointerId(i), new float[]{event.getX(i), event.getY(i), event.getX(i), event.getY(i)});
            fingers = pointers.size();
        }
        for (int i = 0; i < event.getPointerCount(); i++) {
            float[] p = pointers.get(event.getPointerId(i));
            if (p == null) continue;
            p[2] = event.getX(i); p[3] = event.getY(i);
            if (Math.hypot(p[2] - p[0], p[3] - p[1]) > slop) moved = true;
        }
        if (action != MotionEvent.ACTION_UP) return true;
        if (hold != null) handler.removeCallbacks(hold);
        if (invalid || fingers == 0) return true;
        float dx = 0, dy = 0;
        for (float[] p : pointers.values()) { dx += p[2] - p[0]; dy += p[3] - p[1]; }
        dx /= fingers; dy /= fingers;
        if (Math.max(Math.abs(dx), Math.abs(dy)) >= distance) {
            flushPending();
            boolean horizontal = Math.abs(dx) > Math.abs(dy) * 1.4f;
            boolean vertical = Math.abs(dy) > Math.abs(dx) * 1.4f;
            if (!horizontal && !vertical) return true;
            // Opposing fingers (pinch/rotation) and partial lifts are not directional swipes.
            for (float[] p : pointers.values()) {
                float component = horizontal ? p[2] - p[0] : p[3] - p[1];
                float total = horizontal ? dx : dy;
                if (component * total <= 0 || Math.abs(component) < distance * .6f) return true;
            }
            listener.onGesture(fingers, horizontal ? (dx > 0 ? "right" : "left") : (dy > 0 ? "down" : "up"));
        } else if (!moved && event.getEventTime() - downTime <= TAP) {
            if (fingers >= 3) { flushPending(); listener.onGesture(fingers, "tap"); }
            else if (pending != null && pendingFingers == fingers && downTime - pendingTime <= TAP) {
                handler.removeCallbacks(pending); pending = null; listener.onGesture(fingers, "double");
            } else {
                flushPending(); pendingFingers = fingers; pendingTime = event.getEventTime();
                pending = () -> { int count = pendingFingers; pending = null; listener.onGesture(count, "tap"); };
                handler.postDelayed(pending, TAP);
            }
        } else flushPending();
        return true;
    }
    private void flushPending() {
        if (pending != null) {
            handler.removeCallbacks(pending); pending = null; listener.onGesture(pendingFingers, "tap");
        }
    }
}
