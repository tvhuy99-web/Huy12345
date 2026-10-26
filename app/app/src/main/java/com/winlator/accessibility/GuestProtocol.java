package com.winlator.accessibility;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;

public final class GuestProtocol {
    public static final int MAX_FRAME = 1024 * 1024;
    private GuestProtocol() {}

    public static String read(DataInputStream in, int limit) throws IOException {
        int length = in.readInt();
        if (length <= 0 || length > limit || length > MAX_FRAME) throw new IOException("Invalid frame length");
        byte[] data = new byte[length]; in.readFully(data);
        try {
            return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(data)).toString();
        } catch (CharacterCodingException e) { throw new IOException("Invalid UTF-8", e); }
    }
    public static void write(DataOutputStream out, String text) throws IOException {
        byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
        if (bytes.length == 0 || bytes.length > MAX_FRAME) throw new IOException("Invalid outgoing frame");
        out.writeInt(bytes.length); out.write(bytes); out.flush();
    }
    public static String action(long revision, int node, String verb, String value) {
        if (revision < 1 || revision > 0xffffffffL || node < 1 || node > GuestSnapshot.MAX_NODES
                || !(verb.equals("click") || verb.equals("focus") || verb.equals("edit")))
            throw new IllegalArgumentException("Invalid action");
        if (value == null || value.length() > GuestSnapshot.MAX_TEXT || value.indexOf('\0') >= 0)
            throw new IllegalArgumentException("Invalid text");
        byte[] utf8 = value.getBytes(StandardCharsets.UTF_8);
        StringBuilder hex = new StringBuilder(utf8.length * 2);
        final char[] digits = "0123456789abcdef".toCharArray();
        for (byte b : utf8) { hex.append(digits[(b & 255) >>> 4]); hex.append(digits[b & 15]); }
        return "act\t" + revision + "\t" + node + "\t" + verb + "\t" + hex;
    }
}
