package com.winlator.accessibility;

import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** Imports a bounded NVDA journal only after its session matches a fresh live heartbeat. */
public final class NvdaRuntimeDiagnostics {
    private String session="";private long last;
    private final NvdaDiagnosticLog log;
    public NvdaRuntimeDiagnostics() {this(NvdaDiagnosticLog.shared());}
    NvdaRuntimeDiagnostics(NvdaDiagnosticLog log) {this.log=log;}
    public synchronized void collect(File config) {
        try {
            JSONObject status=read(new File(config,"winlator-status.json"));
            long age=System.currentTimeMillis()/1000-status.getLong("heartbeat");
            if(age < -5 || age>15) {
                JSONObject keys=read(new File(config,"winlator-key-status.json"));
                long keyAge=System.currentTimeMillis()/1000-keys.getLong("heartbeat");
                if(keyAge < -5 || keyAge>15 || !status.optString("session").equals(keys.optString("session")))return;
            }
            if(!"ready".equals(status.optString("state")))return;
            accept(read(new File(config,"winlator-diagnostics.json")),status.getString("session"));
        }catch(FileNotFoundException ignored) { }
        catch(Exception e) {NvdaDiagnosticLog.error("diagnostic.import",e);}
    }
    synchronized void accept(JSONObject document,String currentSession) throws Exception {
        if(!currentSession.matches("[a-f0-9]{32}")||!currentSession.equals(document.optString("session"))||document.optInt("version")!=1)return;
        if(!currentSession.equals(session)) {session=currentSession;last=0;log.append("nvda.session","Bắt đầu phiên NVDA");}
        JSONArray events=document.getJSONArray("events");
        for(int i=0;i<events.length();i++) {
            JSONObject event=events.getJSONObject(i);long id=event.getLong("seq");
            if(id<=last)continue;
            if(id>last+1)log.append("nvda.gap","Bản ghi NVDA không nhận kịp: "+(id-last-1));
            log.append("nvda."+event.getString("kind"),"nvda#"+id+"; producerTimeMs="+Math.round(event.optDouble("time",0)*1000)+"; part="+event.optInt("part",1)+"/"+event.optInt("parts",1)+"; "+event.getString("details"));last=id;
        }
    }
    private static JSONObject read(File file) throws Exception {
        try(InputStream in=new FileInputStream(file);ByteArrayOutputStream out=new ByteArrayOutputStream()) {
            byte[] buffer=new byte[4096];int n;
            while((n=in.read(buffer))!=-1) {if(out.size()+n>262144)throw new IOException("Diagnostic frame too large");out.write(buffer,0,n);}
            return new JSONObject(new String(out.toByteArray(),StandardCharsets.UTF_8));
        }
    }
}
