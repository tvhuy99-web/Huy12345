package com.winlator.accessibility;

import android.os.Handler;
import android.view.MotionEvent;
import java.util.*;

/** Pointer-ID tracking, one/two/three taps and two-leg one-finger strokes. */
public final class NvdaGestureRecognizer {
    public interface Listener {void onGesture(int fingers,String gesture);}
    private static final long TAP=300,HOLD=800;
    private final Handler handler;private final Listener listener;
    private final float distance,slop;
    private final Map<Integer,float[]> pointers=new HashMap<>();
    private long downTime,pendingTime;
    private int fingers,pendingFingers,taps;
    private boolean invalid,moved;
    private Runnable pending,hold;
    private String first,second;
    private float pivotX,pivotY,secondPeak;
    public NvdaGestureRecognizer(Handler handler,float density,Listener listener) {
        this.handler=handler;this.listener=listener;distance=48*density;slop=18*density;
    }
    public void cancel() {clearPending();if(hold!=null)handler.removeCallbacks(hold);hold=null;pointers.clear();fingers=0;invalid=true;}
    private void clearPending() {if(pending!=null)handler.removeCallbacks(pending);pending=null;taps=0;}
    private void flushPending() {if(pending!=null) {int count=pendingFingers,number=taps;clearPending();listener.onGesture(count,number==1?"tap":"double");}}
    private static String direction(float dx,float dy) {
        if(Math.abs(dx)>Math.abs(dy)*1.4f)return dx>0?"right":"left";
        if(Math.abs(dy)>Math.abs(dx)*1.4f)return dy>0?"down":"up";
        return null;
    }
    private static float along(String direction,float dx,float dy) {
        switch(direction) {case "up":return -dy;case "down":return dy;case "left":return -dx;default:return dx;}
    }
    private void path(float x,float y) {
        float[] p=pointers.values().iterator().next();
        if(first==null) {
            if(Math.max(Math.abs(x-p[0]),Math.abs(y-p[1]))<distance)return;
            first=direction(x-p[0],y-p[1]);pivotX=x;pivotY=y;return;
        }
        float dx=x-pivotX,dy=y-pivotY;
        if(second==null) {
            String next=direction(dx,dy);
            if(first.equals(next)) {pivotX=x;pivotY=y;}
            else if(next!=null && Math.max(Math.abs(dx),Math.abs(dy))>=distance*.7f) {second=next;secondPeak=along(second,dx,dy);}
        } else {
            float progress=along(second,dx,dy);secondPeak=Math.max(secondPeak,progress);
            float cross=second.equals("up")||second.equals("down")?Math.abs(dx):Math.abs(dy);
            if(secondPeak-progress>distance*.7f || cross>distance)invalid=true;
        }
    }
    public boolean onTouch(MotionEvent event) {
        int action=event.getActionMasked();
        if(action==MotionEvent.ACTION_CANCEL) {cancel();return true;}
        if(action==MotionEvent.ACTION_DOWN) {
            if(pending!=null)handler.removeCallbacks(pending);
            pointers.clear();fingers=0;invalid=moved=false;first=second=null;downTime=event.getEventTime();
            hold=()->{if(!invalid&&!moved&&fingers>=3) {invalid=true;clearPending();listener.onGesture(fingers,"hold");}};
            handler.postDelayed(hold,HOLD);
        }
        if(action==MotionEvent.ACTION_DOWN || action==MotionEvent.ACTION_POINTER_DOWN) {
            int index=event.getActionIndex();
            if(moved || event.getEventTime()-downTime>250 || pointers.size()>=4)invalid=true;
            pointers.put(event.getPointerId(index),new float[]{event.getX(index),event.getY(index),event.getX(index),event.getY(index)});
            fingers=pointers.size();
        }
        for(int h=0;h<=event.getHistorySize();h++) {
            for(int i=0;i<event.getPointerCount();i++) {
                float[] p=pointers.get(event.getPointerId(i));if(p==null)continue;
                float x=h<event.getHistorySize()?event.getHistoricalX(i,h):event.getX(i);
                float y=h<event.getHistorySize()?event.getHistoricalY(i,h):event.getY(i);
                p[2]=x;p[3]=y;if(Math.hypot(x-p[0],y-p[1])>slop)moved=true;
                if(fingers==1)path(x,y);
            }
        }
        if(action!=MotionEvent.ACTION_UP)return true;
        if(hold!=null)handler.removeCallbacks(hold);hold=null;
        if(invalid || fingers==0) {clearPending();return true;}
        if(fingers==1 && first!=null) {
            float[] p=pointers.values().iterator().next();
            if(second==null && along(first,p[2]-p[0],p[3]-p[1])<distance*.6f) {flushPending();return true;}
            if(second!=null && along(second,p[2]-pivotX,p[3]-pivotY)<distance*.6f) {flushPending();return true;}
            flushPending();listener.onGesture(1,first+(second==null?"":"_"+second));return true;
        }
        float dx=0,dy=0;for(float[] p:pointers.values()) {dx+=p[2]-p[0];dy+=p[3]-p[1];}dx/=fingers;dy/=fingers;
        if(Math.max(Math.abs(dx),Math.abs(dy))>=distance) {
            flushPending();String kind=direction(dx,dy);if(kind==null)return true;
            for(float[] p:pointers.values())if(along(kind,p[2]-p[0],p[3]-p[1])<distance*.6f)return true;
            listener.onGesture(fingers,kind);
        } else if(!moved && event.getEventTime()-downTime<=TAP) {
            if(pending!=null && pendingFingers==fingers && downTime-pendingTime<=TAP) {
                taps++;if(taps==3) {int count=fingers;clearPending();listener.onGesture(count,"triple");return true;}
            } else {flushPending();pendingFingers=fingers;taps=1;}
            pendingTime=event.getEventTime();pending=()->{int count=pendingFingers,number=taps;pending=null;taps=0;listener.onGesture(count,number==1?"tap":"double");};handler.postDelayed(pending,TAP);
        } else flushPending();
        return true;
    }
}
