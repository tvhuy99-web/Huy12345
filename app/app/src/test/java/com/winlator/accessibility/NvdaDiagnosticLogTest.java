package com.winlator.accessibility;

import org.junit.Test;
import static org.junit.Assert.*;

public class NvdaDiagnosticLogTest {
    @Test public void errorLocationsAreUsefulWithoutLeakingExceptionMessages() {
        NvdaDiagnosticLog.shared().clear();
        IllegalStateException error=new IllegalStateException("PRIVATE_TYPED_TEXT");
        error.setStackTrace(new StackTraceElement[]{new StackTraceElement("com.winlator.accessibility.NvdaController","shortcut","NvdaController.java",230)});
        NvdaDiagnosticLog.error("command.error",error);
        String report=NvdaDiagnosticLog.shared().snapshot("");
        assertTrue(report.contains("NvdaController.shortcut:230"));assertFalse(report.contains("PRIVATE_TYPED_TEXT"));
    }
    @Test public void evictsOldestEventsAndCountsMetadataWithin500000Characters() {
        NvdaDiagnosticLog log=new NvdaDiagnosticLog();
        log.append("start","OLD_FIRST_EVENT");
        for(int i=0;i<10000;i++)log.append("speech","sentence "+i+" "+"x".repeat(60));
        log.append("last","LATEST_EVENT");
        String report=log.snapshot("device and version");
        assertTrue(report.length()<=500000);assertTrue(report.startsWith("device and version"));
        assertFalse(report.contains("OLD_FIRST_EVENT"));assertFalse(report.contains("sentence 0 "));
        assertTrue(report.contains("LATEST_EVENT"));assertTrue(report.contains("sentence 9999 "));
    }
    @Test public void longSpeechIsChunkedAndUnicodeSurrogatePairsStayIntact() {
        NvdaDiagnosticLog log=new NvdaDiagnosticLog();String text="a".repeat(3999)+"😀"+"ế".repeat(5000)+"FINAL";
        log.append("speech",text);String report=log.snapshot("");
        assertTrue(report.contains("😀"));assertTrue(report.contains("FINAL"));
        for(int i=0;i<report.length();i++)if(Character.isHighSurrogate(report.charAt(i)))assertTrue(Character.isLowSurrogate(report.charAt(++i)));
        assertEquals(5000,report.chars().filter(c->c=='ế').count());
    }
    @Test public void directlyTypedCharactersAndPayloadsAreHiddenButControlKeysRemainUseful() {
        assertFalse(NvdaDiagnosticLog.action("text","PRIVATE_PASSWORD").contains("PRIVATE_PASSWORD"));
        assertFalse(NvdaDiagnosticLog.action("message","PRIVATE_PAYLOAD").contains("PRIVATE_PAYLOAD"));
        assertEquals("[phím nhập liệu đã che]",NvdaDiagnosticLog.shortcut("A"));
        assertEquals("[phím nhập liệu đã che]",NvdaDiagnosticLog.shortcut("Shift+A"));
        assertEquals("[tổ hợp không hợp lệ]",NvdaDiagnosticLog.shortcut("a password"));
        assertEquals("windows+d",NvdaDiagnosticLog.shortcut("Windows+D"));assertEquals("tab",NvdaDiagnosticLog.shortcut("Tab"));
    }
    @Test public void clearAndConcurrentWritersKeepTheBoundAndOrder() throws Exception {
        NvdaDiagnosticLog log=new NvdaDiagnosticLog();Thread[] writers=new Thread[4];
        for(int i=0;i<writers.length;i++) {writers[i]=new Thread(()->{for(int n=0;n<1500;n++)log.append("worker","event "+n);});writers[i].start();}
        for(Thread writer:writers)writer.join();
        String report=log.snapshot("");assertTrue(report.length()<=500000);assertTrue(report.contains("#6000 "));
        log.clear();assertFalse(log.snapshot("").contains("[worker]"));
    }
}
