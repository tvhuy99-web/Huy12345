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
        assertTrue(report.startsWith("Chẩn đoán cử chỉ Winlator"));assertTrue(report.contains("Thiết bị:"));
        assertTrue(report.endsWith(details));assertFalse(report.contains("previous clipboard"));
        assertEquals("Chẩn đoán cử chỉ",clip.getDescription().getLabel().toString());
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
