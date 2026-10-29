package com.winlator.accessibility;

import org.json.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class NvdaRuntimeDiagnosticsTest {
    private static final String SESSION="1234567890abcdef1234567890abcdef";
    private JSONObject document(String session,long... ids) throws Exception {
        JSONArray events=new JSONArray();
        for(long id:ids)events.put(new JSONObject().put("seq",id).put("time",123.5).put("kind","context").put("details","EVENT_"+id));
        return new JSONObject().put("version",1).put("session",session).put("events",events);
    }
    @Test public void importsOnceAndRejectsAnotherNvdaSession() throws Exception {
        NvdaDiagnosticLog log=new NvdaDiagnosticLog();NvdaRuntimeDiagnostics reader=new NvdaRuntimeDiagnostics(log);
        reader.accept(document(SESSION,1,2),SESSION);reader.accept(document(SESSION,1,2),SESSION);
        reader.accept(document("00000000000000000000000000000000",3),SESSION);
        String report=log.snapshot("");assertEquals(1,report.split("EVENT_1",-1).length-1);assertFalse(report.contains("EVENT_3"));
    }
    @Test public void reportsDroppedTelemetryAndAcceptsNewSessionFromSequenceOne() throws Exception {
        NvdaDiagnosticLog log=new NvdaDiagnosticLog();NvdaRuntimeDiagnostics reader=new NvdaRuntimeDiagnostics(log);
        reader.accept(document(SESSION,1,5),SESSION);
        assertTrue(log.snapshot("").contains("không nhận kịp: 3"));
        String next="abcdef0123456789abcdef0123456789";
        reader.accept(document(next,1),next);
        assertEquals(2,log.snapshot("").split("EVENT_1",-1).length-1);
    }
}
