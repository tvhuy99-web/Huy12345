package com.winlator.accessibility;

import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

/** One outstanding command at a time, acknowledged by the NVDA add-on itself. */
public final class NvdaCommandChannel {
    private final File config;
    public NvdaCommandChannel(File config) { this.config = config; }

    public boolean send(String action, String text) throws Exception {
        JSONObject state = read(new File(config, "winlator-status.json"));
        long now = System.currentTimeMillis();
        long age = now - state.getLong("heartbeat") * 1000;
        if (state.optInt("commandProtocol") != 1 || age < -5000 || age > 15000
                || !"ready".equals(state.optString("state"))) return false;
        String session = state.getString("session"), id = UUID.randomUUID().toString();
        if (!session.matches("[a-f0-9]{32}") || text.length() > 512) return false;
        JSONObject command = new JSONObject().put("version", 1).put("session", session)
                .put("id", id).put("created", now / 1000.0).put("action", action).put("text", text);
        File target = new File(config, "winlator-command.json");
        File temporary = new File(config, "winlator-command.tmp");
        try (OutputStream out = new FileOutputStream(temporary)) {
            out.write(command.toString().getBytes(StandardCharsets.UTF_8));
        }
        if (!temporary.renameTo(target)) { temporary.delete(); throw new IOException("Cannot publish NVDA command"); }
        long deadline = System.nanoTime() + 2500000000L;
        try {
            while (System.nanoTime() < deadline) {
                if (Thread.currentThread().isInterrupted()) throw new InterruptedException();
                try {
                    JSONObject reply = read(new File(config, "winlator-reply.json"));
                    if (id.equals(reply.optString("id")) && session.equals(reply.optString("session")))
                        return reply.optBoolean("ok", false);
                } catch (IOException | org.json.JSONException ignored) { }
                Thread.sleep(25);
            }
            return false;
        } finally {
            // A timed-out gesture must never execute later, after a restart or focus change.
            try { if (id.equals(read(target).optString("id"))) target.delete(); }
            catch (IOException | org.json.JSONException ignored) { }
        }
    }

    private static JSONObject read(File file) throws Exception {
        try (InputStream in = new FileInputStream(file); ByteArrayOutputStream bytes = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[1024]; int n;
            while ((n = in.read(buffer)) != -1) {
                if (bytes.size() + n > 4096) throw new IOException("NVDA message too large");
                bytes.write(buffer, 0, n);
            }
            return new JSONObject(bytes.toString("UTF-8"));
        }
    }
}
