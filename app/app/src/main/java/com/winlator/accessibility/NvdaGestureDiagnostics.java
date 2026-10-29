package com.winlator.accessibility;

import android.content.*;
import android.content.pm.PackageInfo;
import android.os.Build;
import androidx.core.content.FileProvider;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** Explicit local copy/export of the shared bounded history. Never sends a message automatically. */
public final class NvdaGestureDiagnostics {
    private NvdaGestureDiagnostics() { }
    static String report(Context context,String details) throws Exception {
        PackageInfo info=context.getPackageManager().getPackageInfo(context.getPackageName(),0);
        String header="Nhật ký công cụ Winlator "+info.versionName+" ("+info.versionCode+")"
            +"\nThiết bị: "+Build.MANUFACTURER+" "+Build.MODEL
            +"; Android "+Build.VERSION.RELEASE+"; API "+Build.VERSION.SDK_INT
            +"\nGhi từ lần mở ứng dụng này; thời gian UTC. Nội dung gõ trực tiếp và ô mật khẩu được che.\n"+details;
        return NvdaDiagnosticLog.shared().snapshot(header);
    }
    public static boolean copy(Context context,String details) {
        try {
            String value=report(context,details);
            // Android Binder may reject a large ClipData. Export the complete history instead.
            if(value.length()>100000)return shareReport(context,value);
            ClipboardManager clipboard=(ClipboardManager)context.getSystemService(Context.CLIPBOARD_SERVICE);
            clipboard.setPrimaryClip(ClipData.newPlainText("Nhật ký công cụ",value));
            NvdaDiagnosticLog.record("diagnostic.copy","Đã sao chép; ký tự="+value.length());return true;
        }catch(Exception e) {NvdaDiagnosticLog.error("diagnostic.copy.failed",e);return false;}
    }
    public static boolean share(Context context,String details) {
        try {return shareReport(context,report(context,details));}
        catch(Exception e) {NvdaDiagnosticLog.error("diagnostic.share.failed",e);return false;}
    }
    static File writeReport(Context context,String value) throws IOException {
        if(value.length()>NvdaDiagnosticLog.MAX_CHARACTERS)throw new IOException("Diagnostic limit exceeded");
        File directory=new File(context.getFilesDir(),"diagnostics");
        if(!directory.isDirectory()&&!directory.mkdirs())throw new IOException("Cannot create diagnostic folder");
        File file=new File(directory,"nhat-ky-winlator.txt");
        try(Writer writer=new OutputStreamWriter(new FileOutputStream(file),StandardCharsets.UTF_8)) {writer.write(value);}
        return file;
    }
    private static boolean shareReport(Context context,String value) throws Exception {
        File file=writeReport(context,value);
        android.net.Uri uri=FileProvider.getUriForFile(context,context.getPackageName()+".FileProvider",file);
        Intent send=new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_STREAM,uri)
            .setClipData(ClipData.newRawUri("Nhật ký công cụ",uri)).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        Intent chooser=Intent.createChooser(send,"Chia sẻ nhật ký công cụ");
        if(!(context instanceof android.app.Activity))chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(chooser);
        NvdaDiagnosticLog.record("diagnostic.share","Đã mở bảng chia sẻ; ký tự="+value.length());return true;
    }
}
