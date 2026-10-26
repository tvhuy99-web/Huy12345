package com.winlator.accessibility;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 28)
public class GuestBridgeTest {
    private JSONObject node(int id) throws JSONException {
        return new JSONObject().put("id", id).put("role", 42).put("state", 0)
                .put("name", "Tên").put("value", "Tiếng Việt")
                .put("source", "msaa").put("click", false).put("edit", true).put("password", false);
    }
    private JSONObject snapshot(JSONArray nodes) throws JSONException {
        return new JSONObject().put("version", 1).put("revision", 2).put("result", 0)
                .put("title", "Cửa sổ").put("window", "1001").put("limited", false)
                .put("nodes", nodes).put("windows", new JSONArray().put(new JSONObject().put("id", "1001").put("name", "Cửa sổ")));
    }
    @Test public void unicodeFramingRoundTrip() throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        GuestProtocol.write(new DataOutputStream(bytes), "Tên\nTiếng Việt");
        assertEquals("Tên\nTiếng Việt", GuestProtocol.read(new DataInputStream(new ByteArrayInputStream(bytes.toByteArray())), 1024));
    }
    @Test public void rejectsOversizedNegativeAndTruncatedFrames() throws Exception {
        for (int length : new int[]{-1, 0, GuestProtocol.MAX_FRAME + 1, 12}) {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            new DataOutputStream(bytes).writeInt(length);
            try {
                GuestProtocol.read(new DataInputStream(new ByteArrayInputStream(bytes.toByteArray())), GuestProtocol.MAX_FRAME);
                fail("Accepted frame " + length);
            } catch (IOException expected) { }
        }
    }
    @Test public void rejectsMalformedUtf8() throws Exception {
        byte[] bytes = {0,0,0,2,(byte)0xc3,0x28};
        try { GuestProtocol.read(new DataInputStream(new ByteArrayInputStream(bytes)), 100); fail(); }
        catch (IOException expected) { }
    }
    @Test public void encodesTextWithoutProtocolInjectionAndRejectsUnsupportedActions() {
        String action = GuestProtocol.action(2, 1, "edit", "a\t\nĐ");
        assertEquals("act\t2\t1\tedit\t61090ac490", action);
        assertEquals("act\t2\t1\tedit\t", GuestProtocol.action(2, 1, "edit", ""));
        for (String verb : new String[]{"exec", "click\nquit", ""}) {
            try { GuestProtocol.action(2,1,verb,""); fail(); } catch (IllegalArgumentException expected) { }
        }
        try { GuestProtocol.action(2,1,"edit","a\0b"); fail(); } catch (IllegalArgumentException expected) { }
    }
    @Test public void parsesUnicodeAndProtectsPasswordsEvenIfGuestSendsValue() throws Exception {
        GuestSnapshot snapshot = new GuestSnapshot(snapshot(new JSONArray().put(node(1))).toString());
        assertEquals("Tên", snapshot.nodes.get(0).name);
        assertEquals("Tiếng Việt", snapshot.nodes.get(0).value);
        JSONObject password = node(1).put("password", true).put("value", "must not reach UI");
        GuestSnapshot protectedSnapshot = new GuestSnapshot(snapshot(new JSONArray().put(password)).toString());
        assertEquals("", protectedSnapshot.nodes.get(0).value);
        assertFalse(protectedSnapshot.nodes.get(0).edit);
    }
    @Test public void rejectsDuplicateIdsUnknownVersionAndUnsafeWindowHandles() throws Exception {
        JSONObject[] invalid = {
            snapshot(new JSONArray().put(node(1)).put(node(1))),
            snapshot(new JSONArray()).put("version", 2),
            snapshot(new JSONArray()).put("window", "1001\tquit"),
            snapshot(new JSONArray()).put("revision", -1)
        };
        for (JSONObject json : invalid) {
            try { new GuestSnapshot(json.toString()); fail("Accepted invalid tree"); } catch (JSONException expected) { }
        }
    }
    @Test public void limitsGuestTreeAndTextAndReadsControlStates() throws Exception {
        JSONArray nodes = new JSONArray();
        for (int i=1; i<=257; i++) nodes.put(node(i));
        try { new GuestSnapshot(snapshot(nodes).toString()); fail(); } catch (JSONException expected) { }
        StringBuilder text = new StringBuilder(); for(int i=0; i<2048; i++) text.append('a');
        try { new GuestSnapshot(snapshot(new JSONArray().put(node(1).put("name", text.toString()))).toString()); fail(); }
        catch (JSONException expected) { }
        GuestSnapshot s = new GuestSnapshot(snapshot(new JSONArray().put(node(1).put("state", 1|2|4|16))).toString());
        assertFalse(s.nodes.get(0).enabled()); assertTrue(s.nodes.get(0).checked());
        assertTrue(s.nodes.get(0).selected()); assertTrue(s.nodes.get(0).focused());
    }
}
