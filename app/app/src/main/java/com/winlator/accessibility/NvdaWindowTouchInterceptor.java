package com.winlator.accessibility;

import android.view.View;
import android.view.ViewGroup;
import android.view.ViewParent;
import android.view.Window;

/** Requests interception at the window, as in GnollHack, bypassing child-view caches. */
public final class NvdaWindowTouchInterceptor {
    private final View decor;
    private int calls;
    private boolean lastRequest,lastCallApplied;
    public NvdaWindowTouchInterceptor(Window window) {this(window.getDecorView());}
    NvdaWindowTouchInterceptor(View decor) {this.decor=decor;}
    public void request(boolean disallow) {
        calls++;lastRequest=disallow;lastCallApplied=false;
        try {
            if(decor instanceof ViewGroup) {
                ((ViewGroup)decor).requestDisallowInterceptTouchEvent(disallow);lastCallApplied=true;
            } else {
                ViewParent parent=decor==null?null:decor.getParent();
                if(parent!=null) {parent.requestDisallowInterceptTouchEvent(disallow);lastCallApplied=true;}
            }
        }catch(RuntimeException ignored) { }
    }
    public String diagnostics() {
        return "Chặn tách chạm tại DecorView: lượt gọi="+calls+"; yêu cầu cuối="+lastRequest+"; đã gọi được="+lastCallApplied;
    }
}
