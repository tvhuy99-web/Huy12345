package com.winlator.xserver.requests;

import static com.winlator.xserver.Keyboard.KEYSYMS_PER_KEYCODE;
import static com.winlator.xserver.XClientRequestHandler.RESPONSE_CODE_SUCCESS;

import com.winlator.xconnector.XInputStream;
import com.winlator.xconnector.XOutputStream;
import com.winlator.xconnector.XStreamLock;
import com.winlator.xserver.Keyboard;
import com.winlator.xserver.XClient;
import com.winlator.xserver.errors.XRequestError;
import com.winlator.xserver.errors.BadValue;

import java.io.IOException;

public abstract class KeyboardRequests {
    public static void getKeyboardMapping(XClient client, XInputStream inputStream, XOutputStream outputStream) throws IOException, XRequestError {
        int firstKeycode = inputStream.readUnsignedByte();
        int count = inputStream.readUnsignedByte();
        inputStream.skip(2);

        if (firstKeycode < Keyboard.MIN_KEYCODE) throw new BadValue(firstKeycode);
        if (firstKeycode + count > Keyboard.MAX_KEYCODE + 1) throw new BadValue(count);
        int[] keysyms = client.xServer.keyboard.getKeysyms(firstKeycode, count);

        try (XStreamLock lock = outputStream.lock()) {
            outputStream.writeByte(RESPONSE_CODE_SUCCESS);
            outputStream.writeByte(KEYSYMS_PER_KEYCODE);
            outputStream.writeShort(client.getSequenceNumber());
            outputStream.writeInt(keysyms.length);
            outputStream.writePad(24);

            for (int keysym : keysyms) outputStream.writeInt(keysym);
        }
    }

    public static void getModifierMapping(XClient client, XInputStream inputStream, XOutputStream outputStream) throws IOException, XRequestError {
        try (XStreamLock lock = outputStream.lock()) {
            outputStream.writeByte(RESPONSE_CODE_SUCCESS);
            outputStream.writeByte((byte)2);
            outputStream.writeShort(client.getSequenceNumber());
            outputStream.writeInt(4);
            outputStream.writePad(24);
            for (byte keycode : Keyboard.getModifierKeycodes()) outputStream.writeByte(keycode);
        }
    }
}
