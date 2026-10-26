package com.winlator.accessibility;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Untrusted guest data is bounded and validated before it reaches Android views. */
public final class GuestSnapshot {
    public static final int MAX_NODES = 256;
    public static final int MAX_TEXT = 2047;
    public final long revision;
    public final int result;
    public final String title, window;
    public final boolean limited;
    public final List<Node> nodes;
    public final List<GuestWindow> windows;

    public static final class Node {
        public final int id, role, state;
        public final String name, value, source;
        public final boolean click, edit, password;
        Node(JSONObject o) throws JSONException {
            id = o.getInt("id"); role = o.getInt("role"); state = o.getInt("state");
            if (id < 1 || id > MAX_NODES) throw new JSONException("Invalid node id");
            name = text(o, "name");
            password = o.optBoolean("password");
            value = password ? "" : text(o, "value");
            source = o.getString("source");
            if (!source.equals("msaa") && !source.equals("win32")) throw new JSONException("Invalid source");
            click = o.optBoolean("click"); edit = !password && o.optBoolean("edit");
        }
        public boolean enabled() { return (state & 1) == 0; }
        public boolean checked() { return (state & 16) != 0; }
        public boolean selected() { return (state & 2) != 0; }
        public boolean focused() { return (state & 4) != 0; }
    }
    public static final class GuestWindow {
        public final String id, name;
        GuestWindow(JSONObject o) throws JSONException {
            id = o.getString("id"); name = text(o, "name");
            if (!id.matches("[0-9a-f]{1,16}")) throw new JSONException("Invalid window id");
        }
    }
    public GuestSnapshot(String json) throws JSONException {
        JSONObject o = new JSONObject(json);
        if (o.getInt("version") != 1) throw new JSONException("Unsupported bridge version");
        revision = o.getLong("revision"); result = o.getInt("result");
        if (revision < 1 || revision > 0xffffffffL || result < 0 || result > 4) throw new JSONException("Invalid revision or result");
        title = text(o, "title"); window = o.getString("window"); limited = o.optBoolean("limited");
        if (!window.matches("[0-9a-f]{1,16}")) throw new JSONException("Invalid foreground window");
        JSONArray a = o.getJSONArray("nodes"), w = o.getJSONArray("windows");
        if (a.length() > MAX_NODES || w.length() > 64) throw new JSONException("Tree too large");
        ArrayList<Node> list = new ArrayList<>(); Set<Integer> ids = new HashSet<>();
        for (int i = 0; i < a.length(); i++) {
            Node node = new Node(a.getJSONObject(i));
            if (!ids.add(node.id)) throw new JSONException("Duplicate node id");
            list.add(node);
        }
        ArrayList<GuestWindow> windowList = new ArrayList<>();
        for (int i = 0; i < w.length(); i++) windowList.add(new GuestWindow(w.getJSONObject(i)));
        nodes = Collections.unmodifiableList(list); windows = Collections.unmodifiableList(windowList);
    }
    private static String text(JSONObject o, String key) throws JSONException {
        String s = o.getString(key);
        if (s.length() > MAX_TEXT || s.indexOf('\0') >= 0) throw new JSONException("Invalid text");
        return s;
    }
}
