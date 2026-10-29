package com.winlator.accessibility;

import android.content.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class NvdaGestureDiagnosticsTest {
    @Test public void explicitCopyPutsDeviceMetadataAndExactGestureDetailsOnAndroidClipboard() {
        Context context=RuntimeEnvironment.getApplication();
        ClipboardManager clipboard=(ClipboardManager)context.getSystemService(Context.CLIPBOARD_SERVICE);
        clipboard.setPrimaryClip(ClipData.newPlainText("old","previous clipboard"));
        String details="ngón=3; MOVE3+=0; cuối=CANCEL; nhận=bỏ";
        assertTrue(NvdaGestureDiagnostics.copy(context,details));
        ClipData clip=clipboard.getPrimaryClip();assertNotNull(clip);
        String report=clip.getItemAt(0).getText().toString();
        assertTrue(report.startsWith("Nhật ký công cụ Winlator"));assertTrue(report.contains("Thiết bị:"));
        assertTrue(report.contains(details));assertFalse(report.contains("previous clipboard"));
        assertEquals("Nhật ký công cụ",clip.getDescription().getLabel().toString());
    }
    @Test public void fullUnicodeReportIsExportedWithoutClipboardSizeTruncation() throws Exception {
        Context context=RuntimeEnvironment.getApplication();
        String content="ế😀".repeat(160000)+"END";
        java.io.File file=NvdaGestureDiagnostics.writeReport(context,content);
        assertEquals(content,java.nio.file.Files.readString(file.toPath()));
        assertTrue(content.length()<=500000);
        try {NvdaGestureDiagnostics.writeReport(context,"x".repeat(500001));fail();}catch(java.io.IOException expected) { }
    }
    @Test public void unavailableClipboardDoesNotClaimSuccessOrReplaceAnExistingClip() {
        Context context=RuntimeEnvironment.getApplication();
        ClipboardManager clipboard=(ClipboardManager)context.getSystemService(Context.CLIPBOARD_SERVICE);
        clipboard.setPrimaryClip(ClipData.newPlainText("old","keep this"));
        Context noClipboard=new ContextWrapper(context) {
            @Override public Object getSystemService(String name) {return CLIPBOARD_SERVICE.equals(name)?null:super.getSystemService(name);}
        };
        assertFalse(NvdaGestureDiagnostics.copy(noClipboard,"details"));
        assertEquals("keep this",clipboard.getPrimaryClip().getItemAt(0).getText().toString());
    }
}
