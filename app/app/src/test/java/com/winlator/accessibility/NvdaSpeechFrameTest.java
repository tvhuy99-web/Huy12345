package com.winlator.accessibility;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import java.io.*;
import java.nio.charset.StandardCharsets;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class NvdaSpeechFrameTest {
    @Test public void preservesVietnameseAcrossPartialNetworkReads() throws Exception {
        String text="Ổ đĩa thứ hai. Tiếng Việt.";
        byte[] json=new JSONObject().put("text",text).toString().getBytes(StandardCharsets.UTF_8);
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        out.writeInt(json.length);out.write(json);
        InputStream partial=new ByteArrayInputStream(bytes.toByteArray()) {
            @Override public synchronized int read(byte[] buffer,int off,int len) {return super.read(buffer,off,Math.min(1,len));}
        };
        assertEquals(text,NvdaAndroidSpeech.read(new DataInputStream(partial)).getString("text"));
    }
    @Test public void rejectsInvalidFrameLengthsBeforeAllocatingPayload() throws Exception {
        for(int size:new int[]{-1,0,65537,Integer.MAX_VALUE}) {
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();new DataOutputStream(bytes).writeInt(size);
            try {NvdaAndroidSpeech.read(new DataInputStream(new ByteArrayInputStream(bytes.toByteArray())));fail();}
            catch(IOException expected) { }
        }
    }
}
