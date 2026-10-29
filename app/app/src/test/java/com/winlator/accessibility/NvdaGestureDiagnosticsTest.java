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
        assertEquals(content,new String(java.nio.file.Files.readAllBytes(file.toPath()),java.nio.charset.StandardCharsets.UTF_8));
        assertTrue(content.length()<=500000);
        try {NvdaGestureDiagnostics.writeReport(context,"x".repeat(500001));fail();}catch(java.io.IOException expected) { }
    }
    @Test public void oversizedClipboardReportUsesAReadableGrantedFileUriWithoutLosingHistory() throws Exception {
        android.app.Application context=RuntimeEnvironment.getApplication();
        NvdaDiagnosticLog.shared().clear();
        NvdaDiagnosticLog.shared().append("speech","ế".repeat(150000)+"LAST_SENTENCE");
        ClipboardManager clipboard=(ClipboardManager)context.getSystemService(Context.CLIPBOARD_SERVICE);
        clipboard.setPrimaryClip(ClipData.newPlainText("old","keep clipboard"));
        assertTrue(NvdaGestureDiagnostics.copy(context,"details"));
        Intent chooser=org.robolectric.Shadows.shadowOf(context).getNextStartedActivity();
        assertNotNull(chooser);assertEquals(Intent.ACTION_CHOOSER,chooser.getAction());
        Intent send=chooser.getParcelableExtra(Intent.EXTRA_INTENT);
        assertEquals(Intent.ACTION_SEND,send.getAction());assertEquals("text/plain",send.getType());
        assertTrue((send.getFlags()&Intent.FLAG_GRANT_READ_URI_PERMISSION)!=0);
        android.net.Uri uri=send.getParcelableExtra(Intent.EXTRA_STREAM);
        assertEquals("content",uri.getScheme());assertEquals(uri,send.getClipData().getItemAt(0).getUri());
        String content;
        try(java.io.InputStream input=context.getContentResolver().openInputStream(uri)) {
            content=new String(input.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8);
        }
        assertTrue(content.contains("LAST_SENTENCE"));assertTrue(content.length()<=500000);
        assertTrue(content.chars().filter(c->c=='ế').count()>=150000);
        assertEquals("keep clipboard",clipboard.getPrimaryClip().getItemAt(0).getText().toString());
        NvdaDiagnosticLog.shared().clear();
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
