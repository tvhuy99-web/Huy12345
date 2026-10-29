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
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.RejectedExecutionException;

/** Starts the actual NVDA executable after Wine's command server is ready. */
public final class NvdaController implements AutoCloseable {
    public static final String AUTO_START = "nvda_auto_start";
    public static final String TOUCH_MODE = "nvda_touch_mode";
    private final XServerDisplayActivity activity;
    private final SharedPreferences preferences;
    private final NvdaKeySender keySender;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final ThreadPoolExecutor commands = new ThreadPoolExecutor(1,1,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(16));
    private volatile boolean closed;
    private volatile int generation;
    private int status = R.string.nvda_stopped;
    private boolean starting, ready;
    private volatile boolean active=true;
    private long deadline, resumeGrace;
    private File runtime, base, state;
    private TextView statusView;
    private Dialog dialog;
    private NvdaAndroidSpeech androidSpeech;
    private TextView voiceView;
    private boolean androidSynth;
    private volatile String publishedVoiceEndpoint="";

    public NvdaController(XServerDisplayActivity activity, SharedPreferences preferences) {
        this.activity = activity; this.preferences = preferences;
        keySender=new NvdaKeySender(main,new NvdaKeySender.Sink() {
            public boolean pressed(com.winlator.xserver.XKeycode key) {return activity.getXServer().keyboard.isKeyPressed(key.id);}
            public void press(com.winlator.xserver.XKeycode key) {activity.getXServer().injectKeyPress(key);}
            public void release(com.winlator.xserver.XKeycode key) {activity.getXServer().injectKeyRelease(key);}
        });
        base = new File(activity.getContainer().getRootDir(),".wine/drive_c/winlator-nvda");
        state = new File(base,"config/winlator-status.json");
        try {androidSpeech=new NvdaAndroidSpeech(activity,preferences,this::updateVoiceView);}
        catch(Exception ignored) { }
    }
    public static boolean autoStart(SharedPreferences preferences) { return preferences.getBoolean(AUTO_START,true); }
    public void onWineReady() { if (autoStart(preferences)) start(); }
    public void setActive(boolean active) {
        this.active=active;
        if(androidSpeech!=null)androidSpeech.setActive(active);
        if(!active) {commands.getQueue().clear();keySender.cancel();}
        if(active) {
            deadline=android.os.SystemClock.elapsedRealtime()+60000;
            resumeGrace=android.os.SystemClock.elapsedRealtime()+10000;
        }
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
                File synthDrivers=new File(plugin.getParentFile(),"synthDrivers");
                if(!synthDrivers.isDirectory() && !synthDrivers.mkdirs())throw new IOException("Cannot prepare Android speech driver");
                copyAsset("nvda/winlatorAndroid.py",new File(synthDrivers,"winlatorAndroid.py"),false);
                if(androidSpeech!=null)androidSpeech.awaitReady();
                JSONObject voiceEndpoint=androidSpeech!=null?androidSpeech.endpoint():new JSONObject().put("version",1).put("enabled",false);
                NvdaPackage.write(new File(config,"winlator-android-voice.json"),voiceEndpoint.toString());
                publishedVoiceEndpoint=voiceEndpoint.toString();
                copyAsset("nvda/nvda-launcher.exe",new File(base.getParentFile(),"windows/nvda-launcher.exe"),false);
                main.post(() -> {
                    if (closed || session != generation) return;
                    runtime = installed; state.delete();new File(base,"config/winlator-reply.json").delete();
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
            boolean alive=false, silent=false, isAndroid=false;
            try {
                JSONObject object=new JSONObject(NvdaPackage.read(state));
                long age=System.currentTimeMillis()/1000-object.getLong("heartbeat");
                alive=object.getInt("version")==1 && object.getString("state").equals("ready") && age>=-5 && age<15;
                silent=object.optString("synth").equals("silence");
                isAndroid=object.optString("synth").equals("winlatorAndroid");
            } catch(Exception ignored) { }
            final boolean healthy=alive;
            final boolean silentSynth=silent;
            final boolean usesAndroid=isAndroid;
            main.post(() -> {
                if (closed || session!=generation) return;
                if (healthy) {
                    starting=false;ready=true;androidSynth=usesAndroid;
                    setStatus(silentSynth ? R.string.nvda_silent:usesAndroid && (androidSpeech==null || !androidSpeech.isConnected())?
                        R.string.nvda_android_disconnected:R.string.nvda_ready);
                    updateVoiceView();
                }
                else if (ready && android.os.SystemClock.elapsedRealtime()>resumeGrace
                        || android.os.SystemClock.elapsedRealtime()>deadline) {
                    starting=false;ready=false;setStatus(R.string.nvda_no_response);return;
                }
                main.postDelayed(() -> poll(session),2000);
            });
        });
    }
    public void stop() {
        keySender.cancel();
        if(androidSpeech!=null)androidSpeech.stop();
        commands.getQueue().clear();
        generation++; starting=false;ready=false;
        if(runtime!=null) activity.getWinHandler().exec("C:\\windows\\nvda-launcher.exe","stop "+runtime.getName());
        setStatus(R.string.nvda_stopped);
    }
    public void restart() {
        stop(); final int request=generation;
        main.postDelayed(()-> {if(!closed && generation==request)start();},5000);
    }
    public interface CommandResult { void done(boolean ok); }
    private interface ReplyResult {void done(JSONObject reply);}
    public void command(String action,String text,CommandResult callback) {
        commandReply(action,text,reply->{if(callback!=null)callback.done(reply!=null && reply.optBoolean("ok",false));});
    }
    private void commandReply(String action,String text,ReplyResult callback) {
        if(closed || !active) {callback.done(null);return;}
        final int session=generation;final long queued=android.os.SystemClock.elapsedRealtime();
        try {
            commands.execute(()->{
                JSONObject result=null;
                try {
                    if(!closed && active && session==generation && android.os.SystemClock.elapsedRealtime()-queued<1500)
                        result=new NvdaCommandChannel(new File(base,"config")).exchange(action,text);
                }catch(Exception ignored) { }
                final JSONObject reply=result;
                main.post(()->{if(!closed)callback.done(active && session==generation?reply:null);});
            });
        }catch(RejectedExecutionException e) {callback.done(null);}
    }
    public void shortcut(NvdaShortcut shortcut,CommandResult callback) {
        commandReply("shortcut",shortcut.canonical(),reply->{
            if(reply==null || !reply.optBoolean("ok",false)) {callback.done(false);return;}
            if(!"external".equals(reply.optString("effect"))) {callback.done(true);return;}
            final int session=generation;
            boolean queued=keySender.send(shortcut,()->main.postDelayed(()->{
                if(!closed && active && session==generation)command("external_feedback","",callback);
            },100));
            if(!queued)callback.done(false);
        });
    }
    public void copyRecentSpeech(CommandResult callback) {
        commandReply("copy_last","",reply->{
            String text=reply==null?"":reply.optString("text","");
            if(reply==null || !reply.optBoolean("ok",false) || text.isEmpty() || text.length()>2048) {callback.done(false);return;}
            android.content.ClipboardManager clipboard=(android.content.ClipboardManager)activity.getSystemService(android.content.Context.CLIPBOARD_SERVICE);
            try {
                clipboard.setPrimaryClip(android.content.ClipData.newPlainText("NVDA",text));
                command("message",activity.getString(R.string.nvda_copied),null);callback.done(true);
            }catch(Exception e) {callback.done(false);}
        });
    }
    public boolean hasSpeech() { return ready && status==R.string.nvda_ready; }
    private void updateVoiceView() {
        if(closed)return;
        if(voiceView!=null)voiceView.setText(androidSpeech==null?activity.getString(R.string.nvda_android_missing):androidSpeech.description());
        if(ready && androidSynth) setStatus(androidSpeech!=null && androidSpeech.isConnected()?R.string.nvda_ready:R.string.nvda_android_disconnected);
        if(androidSpeech!=null && new File(base,"config").isDirectory()) {
            worker.execute(()-> {
                try {
                    if(closed)return;
                    String data=androidSpeech.endpoint().toString();
                    if(data.equals(publishedVoiceEndpoint))return;
                    File temporary=new File(base,"config/winlator-android-voice.tmp");
                    NvdaPackage.write(temporary,data);
                    if(temporary.renameTo(new File(base,"config/winlator-android-voice.json")))publishedVoiceEndpoint=data;
                }catch(Exception ignored) { }
            });
        }
    }
    private void voiceTest() {command("android_voice_test");}
    private void chooseVoice() {
        if(androidSpeech==null || !androidSpeech.isReady()) {
            Toast.makeText(activity,R.string.nvda_android_missing,Toast.LENGTH_LONG).show();return;
        }
        String[] names=androidSpeech.voiceNames();
        if(names.length==0) {voiceTest();return;}
        new AlertDialog.Builder(activity).setTitle(R.string.nvda_choose_android_voice).setItems(names,(d,index)-> {
            androidSpeech.selectVoice(index);voiceTest();
        }).setNegativeButton(android.R.string.cancel,null).show();
    }
    public void dismissForTouch() {if(dialog!=null && dialog.isShowing())dialog.dismiss();}
    private void command(String action) {
        command(action,"",ok->{if(!ok)Toast.makeText(activity,R.string.nvda_command_failed,Toast.LENGTH_LONG).show();});
    }
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
        voiceView=new TextView(activity);voiceView.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);root.addView(voiceView);
        updateVoiceView();
        button(root,R.string.nvda_android_test,this::voiceTest);
        button(root,R.string.nvda_choose_android_voice,this::chooseVoice);
        button(root,R.string.nvda_android_settings,()-> {
            try {activity.startActivity(new android.content.Intent("com.android.settings.TTS_SETTINGS"));}
            catch(Exception ignored) {activity.startActivity(new android.content.Intent(android.provider.Settings.ACTION_SETTINGS));}
        });
        CheckBox automatic=new CheckBox(activity);automatic.setText(R.string.nvda_auto_start);automatic.setChecked(autoStart(preferences));root.addView(automatic);
        automatic.setOnCheckedChangeListener((v,checked)->preferences.edit().putBoolean(AUTO_START,checked).apply());
        CheckBox touch=new CheckBox(activity);touch.setText(R.string.nvda_touch_mode);
        touch.setChecked(preferences.getBoolean(TOUCH_MODE,true));root.addView(touch);
        touch.setOnCheckedChangeListener((v,checked)-> {
            preferences.edit().putBoolean(TOUCH_MODE,checked).apply();activity.updateNvdaTouchMode();
        });
        button(root,R.string.nvda_start,this::start);
        button(root,R.string.nvda_stop,this::stop);
        button(root,R.string.nvda_gesture_actions,activity::showNvdaGestureActions);
        button(root,R.string.gestures,()->new NvdaGestureSettingsDialog(activity,activity.getContainer()).show());
        button(root,R.string.nvda_fallback,()-> {dialog.dismiss();activity.showWindowsAccessibility();});
        button(root,R.string.nvda_close,()->dialog.dismiss());
        dialog.setOnDismissListener(d->AccessibilitySupport.restoreFocus(focus));dialog.show();
        if(dialog.getWindow()!=null)dialog.getWindow().setLayout(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.MATCH_PARENT);
        AccessibilitySupport.focusDialog(root);
    }
    @Override public void close() {
        closed=true;keySender.cancel();generation++;main.removeCallbacksAndMessages(null);worker.shutdownNow();commands.shutdownNow();
        if(androidSpeech!=null)androidSpeech.close();
        if(dialog!=null && dialog.isShowing())dialog.dismiss();
    }
}
