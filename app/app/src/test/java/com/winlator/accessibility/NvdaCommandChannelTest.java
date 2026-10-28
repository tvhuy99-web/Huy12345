package com.winlator.accessibility;

import org.json.JSONObject;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import java.io.File;
import java.util.concurrent.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class NvdaCommandChannelTest {
    @Rule public TemporaryFolder temporary=new TemporaryFolder();
    private static final String SESSION="1234567890abcdef1234567890abcdef";
    private File config(long heartbeat,int protocol) throws Exception {
        File dir=temporary.newFolder();
        NvdaPackage.write(new File(dir,"winlator-status.json"),new JSONObject().put("heartbeat",heartbeat)
            .put("state","ready").put("session",SESSION).put("commandProtocol",protocol).toString());return dir;
    }
    @Test public void doesNotSendToOldOrUnresponsiveNvdaProcess() throws Exception {
        File dir=config(System.currentTimeMillis()/1000-60,1);
        assertFalse(new NvdaCommandChannel(dir).send("enter",""));
        assertFalse(new File(dir,"winlator-command.json").exists());
    }
    @Test public void oldAddonCannotPretendToSupportTouchCommands() throws Exception {
        File dir=config(System.currentTimeMillis()/1000,0);
        assertFalse(new NvdaCommandChannel(dir).send("enter",""));
        assertFalse(new File(dir,"winlator-command.json").exists());
    }
    @Test public void onlyMatchingSessionAndRequestCanAcknowledgeAnAction() throws Exception {
        File dir=config(System.currentTimeMillis()/1000,1);
        NvdaPackage.write(new File(dir,"winlator-reply.json"),new JSONObject().put("id","old-request")
            .put("session",SESSION).put("ok",true).toString());
        ExecutorService executor=Executors.newSingleThreadExecutor();
        try {
            Future<Boolean> result=executor.submit(()->new NvdaCommandChannel(dir).send("text","Tiếng Việt"));
            File requestFile=new File(dir,"winlator-command.json");long deadline=System.nanoTime()+2000000000L;
            while(!requestFile.exists() && System.nanoTime()<deadline)Thread.sleep(10);
            JSONObject request=new JSONObject(NvdaPackage.read(requestFile));
            assertEquals("Tiếng Việt",request.getString("text"));assertFalse(result.isDone());
            File temp=new File(dir,"reply.tmp");
            NvdaPackage.write(temp,new JSONObject().put("id",request.getString("id")).put("session",SESSION).put("ok",true).toString());
            assertTrue(temp.renameTo(new File(dir,"winlator-reply.json")));
            assertTrue(result.get(3,TimeUnit.SECONDS));
        } finally {executor.shutdownNow();}
    }
    @Test public void timedOutGestureIsRemovedSoItCannotRunLater() throws Exception {
        File dir=config(System.currentTimeMillis()/1000,1);
        assertFalse(new NvdaCommandChannel(dir).send("enter",""));
        assertFalse(new File(dir,"winlator-command.json").exists());
    }
}
