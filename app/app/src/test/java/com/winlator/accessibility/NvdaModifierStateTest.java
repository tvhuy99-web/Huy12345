package com.winlator.accessibility;
import org.junit.Test;
import static org.junit.Assert.*;
public class NvdaModifierStateTest {
    @Test public void quickRepeatedSwipeMeansOneStandalonePress() {
        NvdaModifierState m=new NvdaModifierState();assertEquals(NvdaModifierState.Effect.HELD,m.toggle("control",100));
        assertEquals(NvdaModifierState.Effect.PRESS_ONCE,m.toggle("control",500));assertFalse(m.isHeld());
    }
    @Test public void laterRepeatCancelsHeldKey() {
        NvdaModifierState m=new NvdaModifierState();m.toggle("windows",100);
        assertEquals(NvdaModifierState.Effect.RELEASED,m.toggle("windows",1000));assertFalse(m.isHeld());
    }
    @Test public void normalKeyConsumesAllPendingModifiersExactlyOnce() {
        NvdaModifierState m=new NvdaModifierState();m.toggle("control",0);m.toggle("shift",100);
        assertEquals("control+shift+c",m.consume(NvdaShortcut.parse("c")).canonical());
        assertEquals("c",m.consume(NvdaShortcut.parse("c")).canonical());
    }
    @Test public void interveningActionBreaksDoubleSwipeButKeepsModifierForKeySelection() {
        NvdaModifierState m=new NvdaModifierState();m.toggle("control",0);m.interruptSequence();
        assertTrue(m.isHeld());assertEquals(NvdaModifierState.Effect.RELEASED,m.toggle("control",300));
    }
    @Test public void cancellationClearsBothHeldAndDoubleSwipeState() {
        NvdaModifierState m=new NvdaModifierState();m.toggle("windows",0);m.clear();
        assertEquals("d",m.consume(NvdaShortcut.parse("d")).canonical());
        assertEquals(NvdaModifierState.Effect.HELD,m.toggle("windows",300));
    }
}
