package com.winlator.accessibility;

import android.app.AlertDialog;
import android.app.Dialog;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.widget.*;
import androidx.core.view.ViewCompat;
import com.winlator.R;
import com.winlator.XServerDisplayActivity;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Starts the actual NVDA executable after Wine's command server is ready. */
public final class NvdaController implements AutoCloseable {
    public static final String AUTO_START = "nvda_auto_start";
    private final XServerDisplayActivity activity;
    private final SharedPreferences preferences;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private volatile boolean closed;
    private int generation, status = R.string.nvda_stopped;
    private boolean starting, ready, active=true;
    private long deadline;
    private File runtime, base, state;
    private TextView statusView;
    private Dialog dialog;

    public NvdaController(XServerDisplayActivity activity, SharedPreferences preferences) {
        this.activity = activity; this.preferences = preferences;
        base = new File(activity.getContainer().getRootDir(),".wine/drive_c/winlator-nvda");
        state = new File(base,"config/winlator-status.json");
    }
    public static boolean autoStart(SharedPreferences preferences) { return preferences.getBoolean(AUTO_START,true); }
    public void onWineReady() { if (autoStart(preferences)) start(); }
    public void setActive(boolean active) {
        this.active=active;
        if(active)deadline=android.os.SystemClock.elapsedRealtime()+60000;
    }
    private void setStatus(int message) {
        status = message; if (statusView != null) statusView.setText(message);
    }
    public void start() {
        if (closed || starting || ready) return;
        starting = true; final int session = ++generation; setStatus(R.string.nvda_preparing);
        worker.execute(() -> {
            try {
                JSONObject manifest;
                try (InputStream in = activity.getAssets().open("nvda/manifest.json")) {
                    ByteArrayOutputStream out = new ByteArrayOutputStream(); byte[] buffer = new byte[4096]; int n;
                    while ((n=in.read(buffer))!=-1) { if(out.size()+n>16384) throw new IOException("Invalid manifest");out.write(buffer,0,n); }
                    manifest = new JSONObject(out.toString("UTF-8"));
                }
                if (base.getParentFile().getUsableSpace() < manifest.getLong("unpackedBytes") + 32L*1024*1024
                        && !hasInstalledRuntime()) throw new IOException("Insufficient storage for NVDA");
                File installed = NvdaPackage.install(base,activity.getAssets().open("nvda/nvda-portable.zip"),
                        manifest.getString("version"),manifest.getString("archiveSha256"));
                File config = new File(base,"config");
                File plugin = new File(config,"addons/winlatorStartup/globalPlugins");
                if (!plugin.isDirectory() && !plugin.mkdirs()) throw new IOException("Cannot prepare NVDA configuration");
                copyAsset("nvda/config-template.ini",new File(config,"nvda.ini"),true);
                copyAsset("nvda/addon-manifest.ini",new File(plugin.getParentFile(),"manifest.ini"),false);
                copyAsset("nvda/winlatorStartup.py",new File(plugin,"winlatorStartup.py"),false);
                copyAsset("nvda/nvda-launcher.exe",new File(base.getParentFile(),"windows/nvda-launcher.exe"),false);
                main.post(() -> {
                    if (closed || session != generation) return;
                    runtime = installed; state.delete();
                    setStatus(R.string.nvda_starting);
                    activity.getWinHandler().exec("C:\\windows\\nvda-launcher.exe","start "+runtime.getName());
                    deadline = android.os.SystemClock.elapsedRealtime()+60000;
                    main.postDelayed(() -> poll(session),1000);
                });
            } catch (Exception e) {
                main.post(() -> { if (!closed && session==generation) { starting=false; setStatus(R.string.nvda_prepare_failed); } });
            }
        });
    }
    private boolean hasInstalledRuntime() {
        File[] files=base.listFiles((dir,name)->name.startsWith("runtime-"));
        return files!=null && files.length>0;
    }
    private void copyAsset(String asset, File to, boolean preserve) throws IOException {
        if (preserve && to.isFile()) return;
        File temp = new File(to.getPath()+".tmp");
        try (InputStream in=activity.getAssets().open(asset); OutputStream out=new FileOutputStream(temp)) {
            byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);
        }
        if (!temp.renameTo(to)) throw new IOException("Cannot update NVDA integration file");
    }
    private void poll(int session) {
        if (closed || session!=generation) return;
        if(!active) {main.postDelayed(()->poll(session),2000);return;}
        worker.execute(() -> {
            boolean alive=false;
            try {
                JSONObject object=new JSONObject(NvdaPackage.read(state));
                long age=System.currentTimeMillis()/1000-object.getLong("heartbeat");
                alive=object.getInt("version")==1 && object.getString("state").equals("ready") && age>=-5 && age<15;
            } catch(Exception ignored) { }
            final boolean healthy=alive;
            main.post(() -> {
                if (closed || session!=generation) return;
                if (healthy) { starting=false;ready=true;setStatus(R.string.nvda_ready); }
                else if (ready || android.os.SystemClock.elapsedRealtime()>deadline) {
                    starting=false;ready=false;setStatus(R.string.nvda_no_response);return;
                }
                main.postDelayed(() -> poll(session),2000);
            });
        });
    }
    public void stop() {
        generation++; starting=false;ready=false;
        if(runtime!=null) activity.getWinHandler().exec("C:\\windows\\nvda-launcher.exe","stop "+runtime.getName());
        setStatus(R.string.nvda_stopped);
    }
    private void key(int... keys) {
        for(int key:keys) activity.getWinHandler().keyboardEvent((byte)key,extended(key));
        for(int i=keys.length-1;i>=0;i--) activity.getWinHandler().keyboardEvent((byte)keys[i],2|extended(keys[i]));
    }
    private static int extended(int key) { return key==0x2d || key>=0x25 && key<=0x28 ? 1:0; }
    private Button button(LinearLayout root,int label,Runnable action) {
        Button b=new Button(activity);b.setText(label);b.setMinHeight(Math.round(48*activity.getResources().getDisplayMetrics().density));
        root.addView(b,new LinearLayout.LayoutParams(-1,-2));b.setOnClickListener(v->action.run());return b;
    }
    public void show() {
        if(closed || activity.isFinishing())return;
        if(dialog!=null && dialog.isShowing())return;
        View focus=AccessibilitySupport.captureFocus(activity);
        dialog=new Dialog(activity);dialog.setTitle(R.string.nvda_title);
        LinearLayout root=new LinearLayout(activity);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(16,12,16,12);
        ScrollView scroll=new ScrollView(activity);scroll.addView(root);dialog.setContentView(scroll);
        ViewCompat.setAccessibilityPaneTitle(root,activity.getString(R.string.nvda_title));
        statusView=new TextView(activity);statusView.setText(status);statusView.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);root.addView(statusView);
        TextView note=new TextView(activity);note.setText(R.string.nvda_instructions);root.addView(note);
        CheckBox automatic=new CheckBox(activity);automatic.setText(R.string.nvda_auto_start);automatic.setChecked(autoStart(preferences));root.addView(automatic);
        automatic.setOnCheckedChangeListener((v,checked)->preferences.edit().putBoolean(AUTO_START,checked).apply());
        button(root,R.string.nvda_start,this::start);
        button(root,R.string.nvda_stop,this::stop);
        button(root,R.string.nvda_restart,()-> {
            stop(); final int request=generation;
            main.postDelayed(()-> {if(!closed && generation==request)start();},5000);
        });
        button(root,R.string.nvda_focus,()->key(0x2d,0x09));
        button(root,R.string.nvda_window,()->key(0x2d,0x42));
        button(root,R.string.nvda_menu,()->key(0x2d,0x4e));
        button(root,R.string.nvda_silence,()->key(0x11));
        button(root,R.string.nvda_next,()->key(0x09));
        button(root,R.string.nvda_previous,()->key(0x10,0x09));
        button(root,R.string.nvda_enter,()->key(0x0d));
        button(root,R.string.nvda_space,()->key(0x20));
        button(root,R.string.nvda_up,()->key(0x26));
        button(root,R.string.nvda_down,()->key(0x28));
        button(root,R.string.nvda_escape,()->key(0x1b));
        button(root,R.string.nvda_fallback,()-> {dialog.dismiss();activity.showWindowsAccessibility();});
        button(root,R.string.nvda_close,()->dialog.dismiss());
        dialog.setOnDismissListener(d->AccessibilitySupport.restoreFocus(focus));dialog.show();
        if(dialog.getWindow()!=null)dialog.getWindow().setLayout(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.MATCH_PARENT);
        AccessibilitySupport.focusDialog(root);
    }
    @Override public void close() {
        closed=true;generation++;main.removeCallbacksAndMessages(null);worker.shutdownNow();
        if(dialog!=null && dialog.isShowing())dialog.dismiss();
    }
}
