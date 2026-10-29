package com.winlator.accessibility;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.pm.PackageInfo;
import android.os.Build;

/** An explicit user action; structural input metadata only, never a background upload. */
public final class NvdaGestureDiagnostics {
    private NvdaGestureDiagnostics() { }
    public static boolean copy(Context context,String details) {
        try {
            PackageInfo info=context.getPackageManager().getPackageInfo(context.getPackageName(),0);
            String report="Chẩn đoán cử chỉ Winlator "+info.versionName+" ("+info.versionCode+")"
                +"\nThiết bị: "+Build.MANUFACTURER+" "+Build.MODEL
                +"; Android "+Build.VERSION.RELEASE+"; API "+Build.VERSION.SDK_INT+"\n"+details;
            ClipboardManager clipboard=(ClipboardManager)context.getSystemService(Context.CLIPBOARD_SERVICE);
            clipboard.setPrimaryClip(ClipData.newPlainText("Chẩn đoán cử chỉ",report));
            return true;
        }catch(Exception e) {return false;}
    }
}
