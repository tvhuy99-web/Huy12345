package com.winlator.accessibility;
import android.os.*;
import com.winlator.xserver.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.*;
import java.time.Duration;
import java.util.*;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;
@RunWith(RobolectricTestRunner.class) @Config(sdk=28) @LooperMode(LooperMode.Mode.PAUSED)
public class NvdaKeySenderTest {
    private static class Output implements NvdaKeySender.Sink {
        Set<XKeycode> held=new HashSet<>();List<String> events=new ArrayList<>();
        public boolean pressed(XKeycode k){return held.contains(k);}
        public void press(XKeycode k){held.add(k);events.add("+"+k.name());}
        public void release(XKeycode k){held.remove(k);events.add("-"+k.name());}
    }
    @Test public void chordsAreOrderedAndNeverOverlap() {
        Output out=new Output();NvdaKeySender sender=new NvdaKeySender(new Handler(Looper.getMainLooper()),out);
        sender.send(NvdaShortcut.parse("Ctrl+C"),()->{});sender.send(NvdaShortcut.parse("Windows+D"),()->{});
        assertEquals(List.of("+KEY_CTRL_L","+KEY_C"),out.events);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(100));
        assertEquals(List.of("+KEY_CTRL_L","+KEY_C","-KEY_C","-KEY_CTRL_L","+KEY_SUPER_L","+KEY_D","-KEY_D","-KEY_SUPER_L"),out.events);
        assertTrue(out.held.isEmpty());
    }
    @Test public void pauseReleasesOwnedKeysAndDiscardsQueuedChords() {
        Output out=new Output();NvdaKeySender sender=new NvdaKeySender(new Handler(Looper.getMainLooper()),out);
        sender.send(NvdaShortcut.parse("Ctrl+C"),()->fail("late callback"));sender.send(NvdaShortcut.parse("Alt+F4"),()->fail("queued callback"));
        sender.cancel();shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));
        assertTrue(out.held.isEmpty());assertFalse(out.events.contains("+KEY_ALT_L"));
    }
    @Test public void physicallyHeldModifierIsNotReleasedByTouch() {
        Output out=new Output();out.held.add(XKeycode.KEY_CTRL_L);
        NvdaKeySender sender=new NvdaKeySender(new Handler(Looper.getMainLooper()),out);
        sender.send(NvdaShortcut.parse("Ctrl+C"),()->{});shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(100));
        assertEquals(List.of("+KEY_C","-KEY_C"),out.events);assertTrue(out.held.contains(XKeycode.KEY_CTRL_L));
    }
    @Test public void windowsHasARealKeysymAndModifierMapping() {
        Keyboard keyboard=Keyboard.createKeyboard(null);assertEquals(65515,keyboard.keysyms[(XKeycode.KEY_SUPER_L.id-Keyboard.MIN_KEYCODE)*2]);
        assertEquals(64,Keyboard.getModifierFlag(XKeycode.KEY_SUPER_L.id));assertFalse(Keyboard.isModifierSticky(XKeycode.KEY_SUPER_L.id));
        byte[] map=Keyboard.getModifierKeycodes();assertEquals(16,map.length);assertEquals(XKeycode.KEY_CTRL_L.id,map[4]);assertEquals(XKeycode.KEY_SUPER_L.id,map[12]);
    }
}
