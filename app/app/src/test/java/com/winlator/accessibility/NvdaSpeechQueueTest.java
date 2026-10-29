package com.winlator.accessibility;

import org.json.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import java.io.IOException;
import java.util.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class NvdaSpeechQueueTest {
    private static final class Output implements NvdaSpeechQueue.Output {
        final List<String> ids=new ArrayList<>(),texts=new ArrayList<>(),events=new ArrayList<>();int stops;
        public boolean utterance(String id,String text,int rate,int pitch,int volume) {ids.add(id);texts.add(text);return true;}
        public void stop() {stops++;}
        public void event(String type,long epoch,int index) {events.add(type+":"+epoch+":"+index);}
    }
    private JSONObject speak(long epoch,String... texts) throws Exception {
        JSONArray parts=new JSONArray();for(int i=0;i<texts.length;i++)parts.put(new JSONObject().put("text",texts[i]).put("index",i+1));
        return new JSONObject().put("type","speak").put("epoch",epoch).put("parts",parts).put("rate",50).put("pitch",50).put("volume",100);
    }
    @Test public void indexesWaitForActualCompletionInSpeechOrder() throws Exception {
        Output out=new Output();NvdaSpeechQueue queue=new NvdaSpeechQueue(out);
        queue.accept(speak(1,"Ổ C","Ổ D"),4000);assertTrue(out.events.isEmpty());
        queue.finished(out.ids.get(1),true);assertTrue(out.events.isEmpty());
        queue.finished(out.ids.get(0),true);
        assertEquals(List.of("index:1:1","index:1:2","done:1:-1"),out.events);
    }
    @Test public void cancelDiscardsOldAudioAndLateCallbacks() throws Exception {
        Output out=new Output();NvdaSpeechQueue queue=new NvdaSpeechQueue(out);
        queue.accept(speak(1,"old"),4000);String old=out.ids.get(0);
        queue.cancel(2);queue.accept(speak(2,"new"),4000);queue.finished(old,true);
        assertTrue(out.events.isEmpty());queue.finished(out.ids.get(1),true);
        assertEquals(List.of("index:2:1","done:2:-1"),out.events);assertTrue(out.stops>=2);
    }
    @Test public void splitsLongTextWithoutBreakingSurrogatesOrEarlyIndexes() throws Exception {
        Output out=new Output();NvdaSpeechQueue queue=new NvdaSpeechQueue(out);
        queue.accept(speak(0,"a😀b"),2);assertEquals(List.of("a","😀","b"),out.texts);
        queue.finished(out.ids.get(0),true);queue.finished(out.ids.get(1),true);assertTrue(out.events.isEmpty());
        queue.finished(out.ids.get(2),true);assertEquals(List.of("index:0:1","done:0:-1"),out.events);
    }
    @Test public void pauseResumesAtLastWordRangeAndIgnoresStoppedCallbacks() throws Exception {
        Output out=new Output();NvdaSpeechQueue queue=new NvdaSpeechQueue(out);
        queue.accept(speak(1,"một hai ba","bốn"),4000);String old=out.ids.get(0);
        queue.range(old,4);queue.pause(true);queue.finished(old,true);assertTrue(out.events.isEmpty());
        queue.pause(false);assertEquals(List.of("một hai ba","bốn","hai ba","bốn"),out.texts);
        queue.finished(out.ids.get(2),true);queue.finished(out.ids.get(3),true);
        assertEquals(List.of("index:1:1","index:1:2","done:1:-1"),out.events);
    }
    @Test public void staleSpeechCannotReturnAfterCancellation() throws Exception {
        Output out=new Output();NvdaSpeechQueue queue=new NvdaSpeechQueue(out);queue.cancel(9);
        queue.accept(speak(8,"stale"),4000);assertTrue(out.texts.isEmpty());
        queue.accept(speak(9,"fresh"),4000);assertEquals(List.of("fresh"),out.texts);
    }
    @Test public void malformedOversizedMessageNeverQueuesPartialSpeech() throws Exception {
        Output out=new Output();NvdaSpeechQueue queue=new NvdaSpeechQueue(out);
        JSONObject invalid=speak(1,"valid","x".repeat(16001));
        try {queue.accept(invalid,4000);fail();}catch(IOException expected) { }
        assertTrue(out.texts.isEmpty());assertTrue(out.events.isEmpty());
    }
    @Test public void synthesisErrorsDoNotReportAnIndexAsSpoken() throws Exception {
        Output out=new Output();NvdaSpeechQueue queue=new NvdaSpeechQueue(out);
        queue.accept(speak(4,"failed"),4000);queue.finished(out.ids.get(0),false);
        assertEquals(List.of("error:4:-1","done:4:-1"),out.events);
    }
}
