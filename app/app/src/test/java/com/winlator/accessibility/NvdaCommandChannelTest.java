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
    private JSONObject awaitRequest(File file) throws Exception {
        long end=System.nanoTime()+3000000000L;
        while(!file.exists()&&System.nanoTime()<end)Thread.sleep(10);
        return new JSONObject(NvdaPackage.read(file));
    }
    private void acknowledge(File dir,String name,JSONObject request) throws Exception {
        File temp=new File(dir,name+".tmp");
        NvdaPackage.write(temp,new JSONObject().put("id",request.getString("id")).put("session",SESSION).put("ok",true).put("effect","external").toString());
        assertTrue(temp.renameTo(new File(dir,name)));
    }
    private void fastStatus(File dir,String session) throws Exception {
        JSONObject main=new JSONObject(NvdaPackage.read(new File(dir,"winlator-status.json"))).put("keyProtocol",1);
        NvdaPackage.write(new File(dir,"winlator-status.json"),main.toString());
        NvdaPackage.write(new File(dir,"winlator-key-status.json"),new JSONObject().put("session",session).put("state","ready")
            .put("commandProtocol",1).put("heartbeat",System.currentTimeMillis()/1000).toString());
    }
    @Test public void slowReadOnlyFeedbackDoesNotBlockTheIndependentKeyMailbox() throws Exception {
        File dir=config(System.currentTimeMillis()/1000,1);fastStatus(dir,SESSION);
        NvdaCommandChannel channel=new NvdaCommandChannel(dir);
        java.util.concurrent.atomic.AtomicBoolean live=new java.util.concurrent.atomic.AtomicBoolean(true);
        ExecutorService executor=Executors.newFixedThreadPool(2);
        try {
            Future<JSONObject> slow=executor.submit(()->channel.exchange("external_feedback","",live::get,0));
            awaitRequest(new File(dir,"winlator-command.json"));
            Future<JSONObject> key=executor.submit(()->channel.exchange("shortcut","enter"));
            JSONObject request=awaitRequest(new File(dir,"winlator-key-command.json"));
            acknowledge(dir,"winlator-key-reply.json",request);
            assertTrue(key.get(1,TimeUnit.SECONDS).optBoolean("ok"));assertFalse(slow.isDone());
            live.set(false);assertNull(slow.get(1,TimeUnit.SECONDS));
        }finally {executor.shutdownNow();}
    }
    @Test public void lifecycleCancellationRemovesAPendingCommandBeforeResume() throws Exception {
        File dir=config(System.currentTimeMillis()/1000,1);fastStatus(dir,SESSION);
        java.util.concurrent.atomic.AtomicBoolean live=new java.util.concurrent.atomic.AtomicBoolean(true);
        ExecutorService executor=Executors.newSingleThreadExecutor();
        try {
            Future<JSONObject> result=executor.submit(()->new NvdaCommandChannel(dir).exchange("shortcut","enter",live::get,0));
            JSONObject request=awaitRequest(new File(dir,"winlator-key-command.json"));live.set(false);
            assertNull(result.get(1,TimeUnit.SECONDS));assertFalse(new File(dir,"winlator-key-command.json").exists());
            assertTrue(new File(dir,"winlator-key-cancel-"+request.getString("id")).isFile());
        }finally {executor.shutdownNow();}
    }
    @Test public void resumeWaitsForFreshHeartbeatBeforePublishingAControlCommand() throws Exception {
        File dir=config(System.currentTimeMillis()/1000-60,1);NvdaCommandChannel channel=new NvdaCommandChannel(dir);
        ExecutorService executor=Executors.newSingleThreadExecutor();
        try {
            Future<JSONObject> result=executor.submit(()->channel.exchange("message","internal",()->true,2000));
            Thread.sleep(100);assertFalse(new File(dir,"winlator-command.json").exists());
            JSONObject state=new JSONObject(NvdaPackage.read(new File(dir,"winlator-status.json"))).put("heartbeat",System.currentTimeMillis()/1000);
            File fresh=new File(dir,"state.tmp");NvdaPackage.write(fresh,state.toString());assertTrue(fresh.renameTo(new File(dir,"winlator-status.json")));
            JSONObject request=awaitRequest(new File(dir,"winlator-command.json"));acknowledge(dir,"winlator-reply.json",request);
            assertTrue(result.get(1,TimeUnit.SECONDS).optBoolean("ok"));
        }finally {executor.shutdownNow();}
    }
    @Test public void keyHeartbeatFromAnotherSessionCannotAuthorizeInput() throws Exception {
        File dir=config(System.currentTimeMillis()/1000,1);fastStatus(dir,"00000000000000000000000000000000");
        assertNull(new NvdaCommandChannel(dir).exchange("shortcut","enter"));
        assertFalse(new File(dir,"winlator-key-command.json").exists());
    }

}
