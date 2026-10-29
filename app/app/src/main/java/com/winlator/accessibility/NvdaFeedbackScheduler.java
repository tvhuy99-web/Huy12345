package com.winlator.accessibility;

import android.os.Handler;

/** Keeps one read-only feedback request in flight and coalesces fast consecutive keys. */
public final class NvdaFeedbackScheduler {
    public interface Reader {void read(String triggerId,Runnable completed);}
    private final Handler handler;private final Reader reader;
    private String latest;private boolean busy;private int epoch;
    private final Runnable start=this::start;
    public NvdaFeedbackScheduler(Handler handler,Reader reader) {this.handler=handler;this.reader=reader;}
    public void request(String triggerId) {
        latest=triggerId;handler.removeCallbacks(start);
        if(!busy)handler.postDelayed(start,160);
    }
    private void start() {
        if(busy||latest==null)return;
        String id=latest;latest=null;busy=true;int ticket=epoch;
        reader.read(id,()->handler.post(()->{
            if(ticket!=epoch)return;
            busy=false;if(latest!=null)handler.postDelayed(start,60);
        }));
    }
    public void cancel() {epoch++;latest=null;busy=false;handler.removeCallbacks(start);}
}
