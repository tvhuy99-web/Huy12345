package com.winlator.accessibility;

import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.function.BooleanSupplier;

/** Independent key/control mailboxes; one outstanding request per mailbox, session-bound. */
public final class NvdaCommandChannel {
    private final File config;
    private final Object controlLock=new Object(),keyLock=new Object();
    public NvdaCommandChannel(File config) {this.config=config;}
    public boolean send(String action,String text) throws Exception {
        JSONObject reply=exchange(action,text);return reply!=null&&reply.optBoolean("ok",false);
    }
    public JSONObject exchange(String action,String text) throws Exception {return exchange(action,text,()->true,0);}
    public JSONObject exchange(String action,String text,BooleanSupplier current,long recoveryWaitMs) throws Exception {
        long began=System.nanoTime(),until=began+Math.max(0,recoveryWaitMs)*1000000L;
        JSONObject state=null;boolean fast=false;
        do {
            if(!current.getAsBoolean()||Thread.currentThread().isInterrupted())return null;
            try {
                JSONObject main=read(new File(config,"winlator-status.json"));
                fast="shortcut".equals(action)&&main.optInt("keyProtocol")==1;
                state=fast?read(new File(config,"winlator-key-status.json")):main;
                if(!main.optString("session").equals(state.optString("session")))state=null;
                if(fresh(state))break;
            }catch(IOException|org.json.JSONException e) {state=null;}
            if(System.nanoTime()>=until)break;
            Thread.sleep(40);
        }while(true);
        if(!fresh(state)) {NvdaDiagnosticLog.record("command.unavailable",action+"; recoveryWaitMs="+((System.nanoTime()-began)/1000000));return null;}
        synchronized(fast?keyLock:controlLock) {
            if(!current.getAsBoolean())return null;
            return transact(action,text,state,fast,current,began);
        }
    }
    public boolean isFresh() {
        try {return fresh(read(new File(config,"winlator-status.json")));}catch(Exception e) {return false;}
    }
    private static boolean fresh(JSONObject state) {
        if(state==null)return false;
        long age=System.currentTimeMillis()-state.optLong("heartbeat")*1000;
        return state.optInt("commandProtocol")==1&&age>=-5000&&age<=15000&&"ready".equals(state.optString("state"))
            &&state.optString("session").matches("[a-f0-9]{32}");
    }
    private JSONObject transact(String action,String text,JSONObject state,boolean fast,BooleanSupplier current,long began) throws Exception {
        String session=state.getString("session"),id=UUID.randomUUID().toString();
        if(text==null||text.length()>512)return null;
        long now=System.currentTimeMillis();
        String prefix=fast?"winlator-key":"winlator";
        File target=new File(config,prefix+"-command.json"),temporary=new File(config,prefix+"-command.tmp"),replyFile=new File(config,prefix+"-reply.json");
        NvdaDiagnosticLog.record("command.send","id="+id+"; channel="+(fast?"keys":"control")+"; waitMs="+((System.nanoTime()-began)/1000000)+"; "+NvdaDiagnosticLog.action(action,text));
        JSONObject command=new JSONObject().put("version",1).put("session",session).put("id",id)
            .put("created",now/1000.0).put("action",action).put("text",text);
        try(OutputStream out=new FileOutputStream(temporary)) {out.write(command.toString().getBytes(StandardCharsets.UTF_8));}
        if(!temporary.renameTo(target)) {temporary.delete();throw new IOException("Cannot publish NVDA command");}
        // Read-only feedback can be delayed during a window transition; it never blocks the key mailbox.
        boolean acknowledged=false;
        long sent=System.nanoTime(),deadline=sent+("external_feedback".equals(action)?5000000000L:3000000000L);
        try {
            while(System.nanoTime()<deadline) {
                if(!current.getAsBoolean()||Thread.currentThread().isInterrupted()) {NvdaDiagnosticLog.record("command.cancelled","id="+id+"; lifecycle changed");return null;}
                try {
                    JSONObject reply=read(replyFile);
                    if(id.equals(reply.optString("id"))&&session.equals(reply.optString("session"))) {
                        acknowledged=true;
                        NvdaDiagnosticLog.record("command.reply","id="+id+"; elapsedMs="+((System.nanoTime()-sent)/1000000)
                            +"; ok="+reply.optBoolean("ok")+"; effect="+reply.optString("effect"));replyFile.delete();return reply;
                    }
                }catch(IOException|org.json.JSONException ignored) { }
                Thread.sleep(20);
            }
            NvdaDiagnosticLog.record("command.timeout","id="+id+"; action="+action+"; elapsedMs="+((System.nanoTime()-sent)/1000000));return null;
        }finally {
            if(fast&&!acknowledged) {
                try(OutputStream ignored=new FileOutputStream(new File(config,"winlator-key-cancel-"+id))) {
                    NvdaDiagnosticLog.record("command.cancel.marker","id="+id);
                }catch(IOException e) {NvdaDiagnosticLog.error("command.cancel.marker.failed",e);}
            }
            try {if(id.equals(read(target).optString("id")))target.delete();}catch(IOException|org.json.JSONException ignored) { }
        }
    }
    private static JSONObject read(File file) throws Exception {
        try(InputStream in=new FileInputStream(file);ByteArrayOutputStream bytes=new ByteArrayOutputStream()) {
            byte[] buffer=new byte[1024];int n;
            while((n=in.read(buffer))!=-1) {if(bytes.size()+n>16384)throw new IOException("NVDA message too large");bytes.write(buffer,0,n);}
            return new JSONObject(bytes.toString("UTF-8"));
        }
    }
}
