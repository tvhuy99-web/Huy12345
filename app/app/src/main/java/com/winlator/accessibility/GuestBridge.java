package com.winlator.accessibility;

import android.os.Handler;
import android.os.Looper;
import com.winlator.XServerDisplayActivity;
import com.winlator.R;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;

/** One authenticated local session, one worker; no network IO on the UI thread. */
public final class GuestBridge implements AutoCloseable {
    public interface Listener {
        void onSnapshot(GuestSnapshot snapshot);
        void onStatus(int message);
    }
    private final XServerDisplayActivity activity;
    private final Listener listener;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ArrayBlockingQueue<String> commands = new ArrayBlockingQueue<>(16);
    private volatile boolean running, polling, ready;
    private volatile ServerSocket server;
    private volatile Socket client;
    private Thread worker;
    private volatile int generation;

    public GuestBridge(XServerDisplayActivity activity, Listener listener) {
        this.activity = activity; this.listener = listener;
    }
    public synchronized void start() {
        if (running) return;
        commands.clear(); ready = false;
        running = true; final int session = ++generation;
        worker = new Thread(() -> runSession(session), "Wine-accessibility"); worker.setDaemon(true); worker.start();
    }
    public void setPolling(boolean enabled) { polling = enabled; }
    public boolean command(String command) { return running && ready && commands.offer(command); }
    private boolean current(int session) { return running && session == generation; }
    private void status(int session, int message) {
        main.post(() -> { if (session == generation) listener.onStatus(message); });
    }
    private void runSession(int session) {
        ServerSocket localServer = null; Socket localClient = null;
        try {
            status(session, R.string.guest_connecting);
            String token = UUID.randomUUID().toString().replace("-", "");
            File folder = new File(activity.getContainer().getRootDir(), ".wine/drive_c/windows");
            if (!folder.isDirectory()) throw new java.io.IOException("Missing Wine prefix");
            File helper = new File(folder, "winlator-a11y.exe");
            try (InputStream input = activity.getAssets().open("accessibility/winlator-a11y.exe");
                 FileOutputStream output = new FileOutputStream(helper)) {
                byte[] buffer = new byte[32768]; int n;
                while ((n = input.read(buffer)) != -1) output.write(buffer, 0, n);
            }
            localServer = new ServerSocket(0, 4, InetAddress.getByName("127.0.0.1"));
            localServer.setSoTimeout(1000);
            synchronized (this) { if (!current(session)) return; server = localServer; }
            int port = localServer.getLocalPort();
            main.post(() -> {
                if (current(session)) activity.getWinHandler().exec("C:\\windows\\winlator-a11y.exe", port + " " + token);
            });
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(60);
            DataInputStream in = null; DataOutputStream out = null;
            while (current(session) && System.nanoTime() < deadline) {
                Socket candidate = null;
                try {
                    candidate = localServer.accept(); candidate.setSoTimeout(2000);
                    DataInputStream candidateIn = new DataInputStream(candidate.getInputStream());
                    String hello = GuestProtocol.read(candidateIn, 128);
                    if (!MessageDigest.isEqual(hello.getBytes(StandardCharsets.UTF_8),
                            ("WINLATOR-A11Y-1 " + token).getBytes(StandardCharsets.UTF_8))) continue;
                    localClient = candidate; candidate = null; in = candidateIn;
                    out = new DataOutputStream(localClient.getOutputStream()); break;
                } catch (SocketTimeoutException ignored) {
                } catch (java.io.IOException invalidClient) {
                    if (!current(session)) return;
                } finally { if (candidate != null) try { candidate.close(); } catch (Exception ignored) {} }
            }
            if (localClient == null) throw new java.io.IOException("Guest did not connect");
            synchronized (this) { if (!current(session)) return; client = localClient; }
            localClient.setSoTimeout(120000); localClient.setTcpNoDelay(true);
            localServer.close();
            String request = "snapshot";
            while (current(session)) {
                GuestProtocol.write(out, request);
                GuestSnapshot snapshot = new GuestSnapshot(GuestProtocol.read(in, GuestProtocol.MAX_FRAME));
                main.post(() -> { if (current(session)) { ready = true; listener.onSnapshot(snapshot); } });
                request = null;
                while (current(session) && request == null) {
                    request = commands.poll(polling ? 800 : 10000, TimeUnit.MILLISECONDS);
                    if (request == null) request = "snapshot";
                }
            }
        } catch (Exception e) {
            if (current(session)) status(session, R.string.guest_disconnected);
        } finally {
            if (localClient != null) try { localClient.close(); } catch (Exception ignored) {}
            if (localServer != null) try { localServer.close(); } catch (Exception ignored) {}
            synchronized (this) { if (session == generation) { running = false; ready = false; client = null; server = null; } }
        }
    }
    @Override public synchronized void close() {
        running = false; ready = false; generation++; commands.clear();
        try { if (client != null) client.close(); } catch (Exception ignored) {}
        try { if (server != null) server.close(); } catch (Exception ignored) {}
        if (worker != null) worker.interrupt();
    }
}
