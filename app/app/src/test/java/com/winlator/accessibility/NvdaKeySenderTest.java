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
    @Test public void mappingContainsBothSymbolsForEveryAdvertisedKeycode() {
        Keyboard keyboard=Keyboard.createKeyboard(null);
        int[] all=keyboard.getKeysyms(8,248);assertEquals(496,all.length);
        assertArrayEquals(new int[]{99,67},keyboard.getKeysyms(Byte.toUnsignedInt(XKeycode.KEY_C.id),1));
        assertArrayEquals(new int[]{65515,0},keyboard.getKeysyms(Byte.toUnsignedInt(XKeycode.KEY_SUPER_L.id),1));
        keyboard.setKeysyms((byte)255,1234,5678);
        assertArrayEquals(new int[]{1234,5678},keyboard.getKeysyms(255,1));
        assertTrue(keyboard.hasKeysym((byte)255,5678));
        assertThrows(IllegalArgumentException.class,()->keyboard.getKeysyms(7,1));
        assertThrows(IllegalArgumentException.class,()->keyboard.getKeysyms(255,2));
    }
    @Test public void failedPhysicalPressReportsFailureWithoutClaimingDelivery() {
        Output out=new Output() {@Override public void press(XKeycode key) {throw new IllegalStateException();}};
        int[] completed={0},failed={0};
        NvdaKeySender sender=new NvdaKeySender(new Handler(Looper.getMainLooper()),out);
        sender.send(NvdaShortcut.parse("Enter"),()->completed[0]++,()->failed[0]++);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(100));
        assertEquals(0,completed[0]);assertEquals(1,failed[0]);assertTrue(out.held.isEmpty());
    }

    @Test public void altAndWindowsChordsCarryTheRealPreEventXModifierState() {
        Keyboard keyboard=Keyboard.createKeyboard(null);List<Integer> states=new ArrayList<>();List<Integer> symbols=new ArrayList<>();
        keyboard.addOnKeyboardListener(new Keyboard.OnKeyboardListener() {
            public void onKeyPress(byte code,int symbol) {states.add(keyboard.eventModifierBits(code,true));symbols.add(keyboard.getKeysyms(Byte.toUnsignedInt(code),1)[0]);}
            public void onKeyRelease(byte code) {states.add(keyboard.eventModifierBits(code,false));}
        });
        NvdaKeySender sender=new NvdaKeySender(new Handler(Looper.getMainLooper()),new NvdaKeySender.Sink() {
            public boolean pressed(XKeycode key) {return keyboard.isKeyPressed(key.id);}
            public void press(XKeycode key) {keyboard.setKeyPress(key.id,0);}
            public void release(XKeycode key) {keyboard.setKeyRelease(key.id);}
        });
        sender.send(NvdaShortcut.parse("Alt+F4"),()->{});
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(100));
        assertEquals(List.of(0,8,8,8),states);assertEquals(List.of(65513,65473),symbols);
        assertEquals(0,keyboard.getModifiersMask().getBits());
        states.clear();symbols.clear();sender.send(NvdaShortcut.parse("Windows+D"),()->{});
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(100));
        assertEquals(List.of(0,64,64,64),states);assertEquals(List.of(65515,100),symbols);
        assertEquals(0,keyboard.getModifiersMask().getBits());
    }
    @Test public void shiftTabKeepsShiftUntilItsReleaseEvent() {
        Keyboard keyboard=Keyboard.createKeyboard(null);keyboard.setKeyPress(XKeycode.KEY_SHIFT_L.id,0);
        assertEquals(0,keyboard.eventModifierBits(XKeycode.KEY_SHIFT_L.id,true));
        assertEquals(1,keyboard.eventModifierBits(XKeycode.KEY_TAB.id,true));
        keyboard.setKeyRelease(XKeycode.KEY_SHIFT_L.id);
        assertEquals(1,keyboard.eventModifierBits(XKeycode.KEY_SHIFT_L.id,false));
        assertEquals(0,keyboard.getModifiersMask().getBits());
    }

}
