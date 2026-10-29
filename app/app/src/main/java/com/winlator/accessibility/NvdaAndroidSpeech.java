package com.winlator.accessibility;

import android.content.Context;
import android.content.SharedPreferences;
import android.media.AudioAttributes;
import android.os.*;
import android.speech.tts.*;
import com.winlator.R;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import java.util.concurrent.*;

/** Local authenticated NVDA synthesizer endpoint. Speech requests and playback outcomes are included in the explicit diagnostic history. */
public final class NvdaAndroidSpeech implements AutoCloseable {
    private final Context context;
    private final SharedPreferences preferences;
    private final Runnable changed;
    private final Handler main=new Handler(Looper.getMainLooper());
    private final ExecutorService network=Executors.newSingleThreadExecutor();
    private final ThreadPoolExecutor events=new ThreadPoolExecutor(1,1,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(256));
    private final CountDownLatch initialized=new CountDownLatch(1);
    private final List<Voice> voices=new ArrayList<>();
    private final String token;
    private final ServerSocket server;
    private volatile Peer peer;
    private volatile boolean closed,ready,active=true,failed;
    private TextToSpeech tts;
    private Voice voice;
    private final NvdaSpeechQueue speech;

    public NvdaAndroidSpeech(Context context,SharedPreferences preferences,Runnable changed) throws IOException {
        this.context=context;this.preferences=preferences;this.changed=changed;
        byte[] bytes=new byte[32];new SecureRandom().nextBytes(bytes);
        StringBuilder hex=new StringBuilder();for(byte b:bytes)hex.append(String.format(Locale.ROOT,"%02x",b&255));token=hex.toString();
        server=new ServerSocket();server.bind(new InetSocketAddress(InetAddress.getByName("127.0.0.1"),0));
        speech=new NvdaSpeechQueue(new NvdaSpeechQueue.Output() {
            public void stop() {NvdaDiagnosticLog.record("tts.stop","Stop queued speech");if(tts!=null)tts.stop();}
            public void event(String type,long epoch,int index) {
                if(type.equals("error")) {failed=true;changed.run();}
                try {
                    JSONObject message=new JSONObject().put("type",type).put("epoch",epoch);
                    if(index>=0)message.put("index",index);
                    emit(peer,message);
                } catch(Exception ignored) { }
            }
            public boolean utterance(String id,String text,int rate,int pitch,int volume) {
                NvdaDiagnosticLog.record("tts.queue","id="+id+"; characters="+text.length()+"; ready="+ready+"; active="+active+"; rate="+rate+"; pitch="+pitch+"; volume="+volume);
                if(!ready || !active || closed)return false;
                tts.setSpeechRate((float)Math.pow(2,(rate-50)/25.0));
                tts.setPitch((float)Math.pow(2,(pitch-50)/50.0));
                if(text.isEmpty())return tts.playSilentUtterance(1,TextToSpeech.QUEUE_ADD,id)==TextToSpeech.SUCCESS;
                Bundle parameters=new Bundle();parameters.putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME,volume/100f);
                return tts.speak(text,TextToSpeech.QUEUE_ADD,parameters,id)==TextToSpeech.SUCCESS;
            }
        });
        tts=new TextToSpeech(context,status->main.post(()-> {
            if(closed)return;
            if(status==TextToSpeech.SUCCESS) {
                tts.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build());
                tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    public void onStart(String id) {NvdaDiagnosticLog.record("tts.start",id);main.post(()->{if(!closed)failed=false;});}
                    public void onDone(String id) {NvdaDiagnosticLog.record("tts.done",id);main.post(()->{if(!closed)speech.finished(id,true);});}
                    public void onError(String id) {NvdaDiagnosticLog.record("tts.error",id);main.post(()->{if(!closed)speech.finished(id,false);});}
                    @Override public void onStop(String id,boolean interrupted) {NvdaDiagnosticLog.record("tts.interrupted",id+"; interrupted="+interrupted);main.post(()->{if(!closed)speech.finished(id,false);});}
                    @Override public void onRangeStart(String id,int start,int end,int frame) {
                        main.post(()->{if(!closed)speech.range(id,start);});
                    }
                });
                chooseVoice();
            }
            initialized.countDown();changed.run();
        }));
        network.execute(this::listen);
    }
    private void chooseVoice() {
        NvdaDiagnosticLog.record("tts.voice","Choosing Vietnamese voice");
        ready=false;voices.clear();
        int language=tts.setLanguage(new Locale("vi","VN"));
        Voice preferred=tts.getVoice();Set<Voice> available=tts.getVoices();
        if(available!=null)for(Voice v:available) {
            if("vi".equals(v.getLocale().getLanguage()) && !v.getFeatures().contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED))voices.add(v);
        }
        String saved=preferences.getString("nvda_android_voice","");
        voices.sort(Comparator.comparing((Voice v)->!v.getName().equals(saved)).thenComparing(Voice::isNetworkConnectionRequired)
            .thenComparing(v->!v.equals(preferred)).thenComparing(Comparator.comparingInt(Voice::getQuality).reversed())
            .thenComparingInt(Voice::getLatency).thenComparing(Voice::getName));
        NvdaDiagnosticLog.record("tts.voices","available="+voices.size());
        if(!voices.isEmpty()) {
            Voice best=voices.get(0);
            if(tts.setVoice(best)==TextToSpeech.SUCCESS) {voice=best;ready=true;}
        } else if(language>=TextToSpeech.LANG_AVAILABLE && available==null) {voice=null;ready=true;}
    }
    public boolean awaitReady() throws InterruptedException {initialized.await(10,TimeUnit.SECONDS);return ready && !closed;}
    public boolean isReady() {return ready && !closed;}
    public boolean isConnected() {return isReady() && peer!=null && !failed;}
    public JSONObject endpoint() throws Exception {
        return new JSONObject().put("version",1).put("enabled",isReady()).put("port",server.getLocalPort()).put("token",token);
    }
    public String description() {
        if(initialized.getCount()>0)return context.getString(R.string.nvda_android_initializing);
        if(!ready)return context.getString(R.string.nvda_android_missing);
        if(failed)return context.getString(R.string.nvda_android_failed);
        String name=voice==null?context.getString(R.string.nvda_android_default):voice.getName();
        return context.getString(voice!=null && voice.isNetworkConnectionRequired()?R.string.nvda_android_network:R.string.nvda_android_offline,name);
    }
    public String[] voiceNames() {
        String[] names=new String[voices.size()];
        for(int i=0;i<names.length;i++)names[i]=(i+1)+". "+voices.get(i).getName()+" — "+
            context.getString(voices.get(i).isNetworkConnectionRequired()?R.string.nvda_voice_online:R.string.nvda_voice_offline);
        return names;
    }
    public void selectVoice(int index) {
        if(index>=0 && index<voices.size() && tts.setVoice(voices.get(index))==TextToSpeech.SUCCESS) {
            voice=voices.get(index);failed=false;changed.run();
            preferences.edit().putString("nvda_android_voice",voice.getName()).apply();
        }
    }
    public void setActive(boolean value) {active=value;if(!value)speech.reset();}
    public void stop() {speech.reset();}
    private void listen() {
        while(!closed) {
            Peer candidate=null;
            try {
                candidate=new Peer(server.accept());candidate.socket.setSoTimeout(2000);
                JSONObject hello=read(candidate.input);
                if(!ready || !active || hello.optInt("version")!=1 || !hello.optString("type").equals("hello") ||
                    !MessageDigest.isEqual(token.getBytes(StandardCharsets.US_ASCII),hello.optString("token").getBytes(StandardCharsets.US_ASCII)))
                    throw new IOException("Speech handshake rejected");
                final Peer accepted=candidate;CountDownLatch attached=new CountDownLatch(1);
                main.post(()-> {
                    if(!closed) {NvdaDiagnosticLog.record("tts.connected","Authenticated local NVDA synthesizer");speech.reset();peer=accepted;failed=false;changed.run();}
                    attached.countDown();
                });
                if(!attached.await(2,TimeUnit.SECONDS) || closed)throw new IOException("Speech host unavailable");
                candidate.send(new JSONObject().put("type","ready").put("version",1));candidate.socket.setSoTimeout(15000);
                while(!closed) {
                    JSONObject message=read(candidate.input);
                    if(message.optString("type").equals("ping")) {candidate.send(new JSONObject().put("type","pong"));continue;}
                    main.post(()-> {
                        if(closed || peer!=accepted || !active)return;
                        try {speech.accept(message,Math.min(4000,TextToSpeech.getMaxSpeechInputLength()));}
                        catch(Exception ignored) {speech.reset();failed=true;changed.run();accepted.close();}
                    });
                }
            } catch(Exception e) {if(!closed)NvdaDiagnosticLog.error("tts.connection",e);}
            finally {
                if(candidate!=null)candidate.close();
                final Peer old=candidate;
                main.post(()->{if(!closed && peer==old) {speech.reset();peer=null;changed.run();}});
            }
        }
    }
    private void emit(Peer recipient,JSONObject message) {
        if(recipient==null || closed)return;
        try {events.execute(()->{try {recipient.send(message);}catch(Exception ignored){recipient.close();}});}
        catch(RejectedExecutionException ignored) {recipient.close();}
    }
    static JSONObject read(DataInputStream input) throws Exception {
        int size=input.readInt();if(size<1 || size>65536)throw new IOException("Invalid speech frame");
        byte[] bytes=new byte[size];input.readFully(bytes);return new JSONObject(new String(bytes,StandardCharsets.UTF_8));
    }
    private static final class Peer {
        final Socket socket;final DataInputStream input;final DataOutputStream output;
        Peer(Socket socket) throws IOException {
            this.socket=socket;socket.setTcpNoDelay(true);input=new DataInputStream(new BufferedInputStream(socket.getInputStream()));
            output=new DataOutputStream(socket.getOutputStream());
        }
        synchronized void send(JSONObject value) throws Exception {
            byte[] bytes=value.toString().getBytes(StandardCharsets.UTF_8);
            if(bytes.length>65536)throw new IOException("Speech frame too large");output.writeInt(bytes.length);output.write(bytes);output.flush();
        }
        void close() {try {socket.close();}catch(IOException ignored){}}
    }
    @Override public void close() {
        if(closed)return;closed=true;initialized.countDown();
        try {server.close();}catch(IOException ignored) { }
        if(peer!=null)peer.close();speech.reset();network.shutdownNow();events.shutdownNow();
        if(tts!=null)tts.shutdown();
    }
}
