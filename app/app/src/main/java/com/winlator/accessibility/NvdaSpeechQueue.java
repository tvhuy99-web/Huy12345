package com.winlator.accessibility;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.IOException;
import java.util.*;

/** Speech ordering and cancellation, independent of an installed Android voice. Single-threaded. */
public final class NvdaSpeechQueue {
    public interface Output {
        boolean utterance(String id,String text,int rate,int pitch,int volume);
        void stop();
        void event(String type,long epoch,int index);
    }
    private static final class Part {
        String text; int index,rate,pitch,volume,start;
        boolean complete,success,cancelled;
        Part(String text,int index,int rate,int pitch,int volume) {
            this.text=text;this.index=index;this.rate=rate;this.pitch=pitch;this.volume=volume;
        }
    }
    private final Output output;
    private final LinkedHashMap<String,Part> pending=new LinkedHashMap<>();
    private final List<Part> pausedParts=new ArrayList<>();
    private long epoch=-1, serial;
    private boolean paused;
    public NvdaSpeechQueue(Output output) {this.output=output;}
    public void cancel(long next) {
        if(next<epoch)return;
        epoch=next;pending.clear();pausedParts.clear();paused=false;output.stop();
    }
    public void reset() {pending.clear();pausedParts.clear();paused=false;epoch=-1;output.stop();}
    public void accept(JSONObject message,int maxText) throws Exception {
        String type=message.getString("type");long next=message.getLong("epoch");
        if(next<0 || next<epoch)return;
        if(type.equals("cancel")) {cancel(next);return;}
        if(next>epoch)cancel(next);
        if(type.equals("pause")) {pause(message.getBoolean("paused"));return;}
        if(!type.equals("speak"))throw new IOException("Unsupported speech operation");
        JSONArray parts=message.getJSONArray("parts");
        int rate=range(message,"rate"),pitch=range(message,"pitch"),volume=range(message,"volume");
        if(parts.length()>64 || maxText<2)throw new IOException("Speech limit exceeded");
        List<Part> additions=new ArrayList<>();int characters=0;
        for(int i=0;i<parts.length();i++) {
            JSONObject part=parts.getJSONObject(i);String text=part.getString("text");
            characters+=text.length();if(characters>16000)throw new IOException("Speech limit exceeded");
            int index=part.optInt("index",-1);
            if(index < -1)throw new IOException("Invalid speech index");
            if(text.isEmpty())additions.add(new Part("",index,rate,pitch,volume));
            for(int at=0;at<text.length();) {
                int end=Math.min(text.length(),at+maxText);
                if(end<text.length() && Character.isHighSurrogate(text.charAt(end-1)))end--;
                additions.add(new Part(text.substring(at,end),end==text.length()?index:-1,rate,pitch,volume));at=end;
            }
        }
        if(pending.size()+pausedParts.size()+additions.size()>128) {
            cancel(epoch);output.event("error",epoch,-1);output.event("done",epoch,-1);return;
        }
        if(paused)pausedParts.addAll(additions);else enqueue(additions);
    }
    private static int range(JSONObject message,String key) throws Exception {
        int value=message.getInt(key);if(value<0 || value>100)throw new IOException("Invalid speech setting");return value;
    }
    private void enqueue(List<Part> parts) {
        LinkedHashMap<String,Part> fresh=new LinkedHashMap<>();
        for(Part part:parts)fresh.put("nvda-"+(++serial),part);
        pending.putAll(fresh);
        if(parts.isEmpty() && pending.isEmpty())output.event("done",epoch,-1);
        for(Map.Entry<String,Part> entry:fresh.entrySet()) {
            Part part=entry.getValue();
            if(!part.complete && !output.utterance(entry.getKey(),part.text,part.rate,part.pitch,part.volume))finished(entry.getKey(),false);
        }
        if(!parts.isEmpty())drain();
    }
    public void finished(String id,boolean success) {
        Part part=pending.get(id);if(part==null)return;
        part.complete=true;part.success=success;drain();
    }
    public void interrupted(String id) {
        Part part=pending.get(id);if(part==null)return;
        part.complete=true;part.success=false;part.cancelled=true;drain();
    }
    private void drain() {
        boolean removed=false;
        Iterator<Map.Entry<String,Part>> iterator=pending.entrySet().iterator();
        while(iterator.hasNext()) {
            Part part=iterator.next().getValue();if(!part.complete)break;
            iterator.remove();removed=true;
            if(part.success && part.index>=0)output.event("index",epoch,part.index);
            if(!part.success&&!part.cancelled)output.event("error",epoch,-1);
        }
        if(removed && pending.isEmpty())output.event("done",epoch,-1);
    }
    public void range(String id,int start) {
        Part part=pending.get(id);if(part!=null)part.start=Math.max(0,Math.min(start,part.text.length()));
    }
    public void pause(boolean value) {
        if(value==paused)return;
        paused=value;
        if(value) {
            for(Part part:pending.values()) {part.text=part.text.substring(part.start);part.start=0;pausedParts.add(part);}
            pending.clear();output.stop();
        } else {
            List<Part> parts=new ArrayList<>(pausedParts);pausedParts.clear();enqueue(parts);
        }
    }
}
