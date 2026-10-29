package com.winlator.accessibility;

import android.os.Handler;
import android.view.MotionEvent;
import java.util.*;

/** Tracks a complete contact session, including fingers released before the final UP. */
public final class NvdaGestureRecognizer {
    public interface Listener { void onGesture(int fingers, String gesture); }
    private static final long TAP_MAX=320, MULTI_TAP_MAX=520, TAP_GAP=360, JOIN_MAX=300, SWIPE_MAX=1200;
    private static final float AGREEMENT=.72f;
    private static final class Trace {
        final float startX,startY;
        float x,y,maximumMovement;
        Trace(float x,float y) {startX=this.x=x;startY=this.y=y;}
        void update(float x,float y) {
            this.x=x;this.y=y;
            maximumMovement=Math.max(maximumMovement,(float)Math.hypot(x-startX,y-startY));
        }
    }
    private final Handler handler;
    private final Listener listener;
    private final float distance,slop,density;
    private final ArrayDeque<String> recent=new ArrayDeque<>();
    private String joins="";
    private long lastEventTime;
    private int moveFrames,multiMoveFrames,maximumReceivedFingers;
    private final Map<Integer,Trace> traces=new LinkedHashMap<>();
    private final Set<Integer> active=new HashSet<>();
    private long downTime,pendingTime;
    private int fingers,pendingFingers,taps;
    private boolean session,invalid,released,singlePathInvalid;
    private Runnable pending;
    private String first,second;
    private float pivotX,pivotY,secondPeak;

    public NvdaGestureRecognizer(Handler handler,float density,Listener listener) {
        this.handler=handler;this.listener=listener;this.density=density>0?density:1;distance=48*this.density;slop=18*this.density;
    }
    public void cancel() {record("LOCAL_CANCEL","bỏ",lastEventTime);clearPending();resetSession();}
    private void resetSession() {session=false;active.clear();traces.clear();}
    private String summary(String end,String result,long time) {
        float dx=0,dy=0;
        for(Trace trace:traces.values()) {dx+=trace.x-trace.startX;dy+=trace.y-trace.startY;}
        int count=Math.max(1,traces.size());
        return "ngón="+fingers+"; đặt="+joins+"; MOVE="+moveFrames+"; MOVE3+="+multiMoveFrames
            +"; cuối="+end+"; ms="+Math.max(0,time-downTime)
            +"; dx="+Math.round(dx/count/density)+"dp; dy="+Math.round(dy/count/density)+"dp; nhận="+result;
    }
    private void record(String end,String result,long time) {
        if(!session||fingers<3)return;
        if(recent.size()==8)recent.removeFirst();
        recent.addLast(summary(end,result,time));
    }
    /** Bounded, memory-only metadata; no absolute coordinates, window text or input content. */
    public String diagnostics() {
        String text="Ngón tối đa đã nhận: "+maximumReceivedFingers+"\n"+String.join("\n",recent);
        if(session&&fingers>=3)text+="\n"+summary("đang chạm","chưa",lastEventTime);
        if(recent.isEmpty()&&!(session&&fingers>=3))text+="\nChưa có chuỗi từ ba ngón.";
        return text;
    }
    private void clearPending() {if(pending!=null)handler.removeCallbacks(pending);pending=null;taps=0;}
    private void flushPending() {
        if(pending!=null) {
            int count=pendingFingers,number=taps;clearPending();
            listener.onGesture(count,number==1?"tap":"double");
        }
    }
    private static String direction(float dx,float dy) {
        if(Math.abs(dx)>Math.abs(dy)*1.4f)return dx>0?"right":"left";
        if(Math.abs(dy)>Math.abs(dx)*1.4f)return dy>0?"down":"up";
        return null;
    }
    private static float along(String direction,float dx,float dy) {
        switch(direction) {case "up":return -dy;case "down":return dy;case "left":return -dx;default:return dx;}
    }
    private void path(float x,float y,Trace p) {
        if(first==null) {
            if(Math.max(Math.abs(x-p.startX),Math.abs(y-p.startY))<distance)return;
            first=direction(x-p.startX,y-p.startY);pivotX=x;pivotY=y;return;
        }
        float dx=x-pivotX,dy=y-pivotY;
        if(second==null) {
            String next=direction(dx,dy);
            if(first.equals(next)) {pivotX=x;pivotY=y;}
            else if(next!=null&&Math.max(Math.abs(dx),Math.abs(dy))>=distance*.7f) {
                second=next;secondPeak=along(second,dx,dy);
            }
        } else {
            float progress=along(second,dx,dy);secondPeak=Math.max(secondPeak,progress);
            float cross=second.equals("up")||second.equals("down")?Math.abs(dx):Math.abs(dy);
            if(secondPeak-progress>distance*.7f||cross>distance)singlePathInvalid=true;
        }
    }
    private boolean still() {
        for(Trace trace:traces.values())if(trace.maximumMovement>slop)return false;
        return true;
    }
    private void updatePositions(MotionEvent event) {
        for(int h=0;h<=event.getHistorySize();h++)for(int i=0;i<event.getPointerCount();i++) {
            int id=event.getPointerId(i);
            Trace trace=traces.get(id);
            if(trace==null||!active.contains(id))continue;
            float x=h<event.getHistorySize()?event.getHistoricalX(i,h):event.getX(i);
            float y=h<event.getHistorySize()?event.getHistoricalY(i,h):event.getY(i);
            trace.update(x,y);
            if(fingers==1)path(x,y,trace);
        }
    }
    private boolean matchesActive(MotionEvent event) {
        if(active.size()!=event.getPointerCount())return false;
        Set<Integer> ids=new HashSet<>();
        for(int i=0;i<event.getPointerCount();i++)ids.add(event.getPointerId(i));
        return ids.equals(active);
    }
    private String classify(long time) {
        long duration=time-downTime;
        if(invalid||duration<0||fingers==0)return null;
        if(still()&&duration<=(fingers==1?TAP_MAX:MULTI_TAP_MAX))return "tap";
        if(duration>SWIPE_MAX)return null;
        if(fingers==1&&first!=null) {
            Trace trace=traces.values().iterator().next();
            if(singlePathInvalid)return null;
            if(second==null&&along(first,trace.x-trace.startX,trace.y-trace.startY)<distance*.6f)return null;
            if(second!=null&&along(second,trace.x-pivotX,trace.y-pivotY)<distance*.6f)return null;
            return first+(second==null?"":"_"+second);
        }
        float dx=0,dy=0,totalLength=0;
        for(Trace trace:traces.values()) {
            float x=trace.x-trace.startX,y=trace.y-trace.startY;
            dx+=x;dy+=y;totalLength+=(float)Math.hypot(x,y);
        }
        if(totalLength/fingers<distance||Math.hypot(dx,dy)<totalLength*AGREEMENT)return null;
        // A hand swipe need not move every finger the same distance. Use its common vector.
        if(fingers>=3)return Math.abs(dx)>=Math.abs(dy)?(dx>0?"right":"left"):(dy>0?"down":"up");
        return direction(dx,dy);
    }
    private void finish(long time) {
        int count=fingers;String kind=classify(time);record("UP",kind==null?"bỏ":kind,time);resetSession();
        if("tap".equals(kind)) {
            if(pending!=null&&pendingFingers==count&&downTime>=pendingTime&&downTime-pendingTime<=TAP_GAP) {
                taps++;
                if(taps==3) {clearPending();listener.onGesture(count,"triple");return;}
            } else {flushPending();pendingFingers=count;taps=1;}
            pendingTime=time;
            pending=()->{
                int tapCount=pendingFingers,number=taps;pending=null;taps=0;
                listener.onGesture(tapCount,number==1?"tap":"double");
            };
            handler.postDelayed(pending,TAP_GAP);
        } else {flushPending();if(kind!=null)listener.onGesture(count,kind);}
    }
    public boolean onTouch(MotionEvent event) {
        int action=event.getActionMasked();
        if(action==MotionEvent.ACTION_CANCEL ||
                (action==MotionEvent.ACTION_POINTER_UP&&(event.getFlags()&MotionEvent.FLAG_CANCELED)!=0)) {
            // CANCEL is not a release. Direction and final finger count may never arrive.
            record(action==MotionEvent.ACTION_CANCEL?"CANCEL":"POINTER_CANCEL","bỏ",event.getEventTime());
            clearPending();resetSession();return true;
        }
        if(action==MotionEvent.ACTION_DOWN) {
            record("NEW_DOWN","bỏ",lastEventTime);resetSession();if(pending!=null)handler.removeCallbacks(pending);
            session=true;fingers=0;invalid=released=singlePathInvalid=false;
            first=second=null;downTime=event.getEventTime();
            joins="";moveFrames=multiMoveFrames=0;
        } else if(!session)return true;

        lastEventTime=event.getEventTime();
        if(action==MotionEvent.ACTION_DOWN||action==MotionEvent.ACTION_POINTER_DOWN) {
            int index=event.getActionIndex(),id=event.getPointerId(index);
            if(released||active.contains(id)||active.size()>=4||event.getEventTime()-downTime>JOIN_MAX)invalid=true;
            traces.put(id,new Trace(event.getX(index),event.getY(index)));active.add(id);
            fingers=Math.max(fingers,active.size());
            maximumReceivedFingers=Math.max(maximumReceivedFingers,fingers);
            if(joins.length()<160)joins+=(joins.isEmpty()?"":">")+active.size()+"@"+(event.getEventTime()-downTime);
        }
        if(!matchesActive(event))invalid=true;
        updatePositions(event);
        if(action==MotionEvent.ACTION_MOVE) {
            moveFrames++;if(fingers>=3&&!released&&active.size()==fingers)multiMoveFrames++;
        }
        if(action==MotionEvent.ACTION_POINTER_UP||action==MotionEvent.ACTION_UP) {
            released=true;active.remove(event.getPointerId(event.getActionIndex()));
            if(action==MotionEvent.ACTION_UP) {
                if(!active.isEmpty())invalid=true;
                finish(event.getEventTime());
            }
        }
        return true;
    }
}
