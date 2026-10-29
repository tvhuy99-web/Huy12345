package com.winlator.accessibility;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;
@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class NvdaGestureBindingsTest {
    @Test public void defaultsCoverAllRequestedGesturesAndNewNavigation() {
        NvdaGestureBindings b=new NvdaGestureBindings("");assertEquals(40,NvdaGestureBindings.gestures().size());
        assertEquals("left",b.action("1:left"));assertEquals("right",b.action("1:right"));
        assertEquals("tab",b.action("2:up"));assertEquals("shift_tab",b.action("2:down"));
        assertEquals("none",b.action("4:tap"));assertEquals("menu",b.action("3:tap"));
        assertEquals("hold_ctrl",b.action("2:left"));assertEquals("hold_windows",b.action("2:right"));
        assertEquals("window",b.action("2:double"));assertEquals("repeat_last",b.action("3:double"));
        assertEquals("copy_last",b.action("4:down"));assertEquals("none",b.action("1:left_up"));
    }
    @Test public void customShortcutPersistsWithoutLeakingIntoAnotherEnvironment() {
        NvdaGestureBindings one=new NvdaGestureBindings(""),two=new NvdaGestureBindings("");
        one.set("1:up","key:ctrl c");assertEquals("key:Ctrl+C",new NvdaGestureBindings(one.json()).action("1:up"));
        assertEquals("up",two.action("1:up"));
    }
    @Test public void explicitUnassignedSurvivesRoundTripAndResetRestoresDefaults() {
        NvdaGestureBindings b=new NvdaGestureBindings("");b.set("3:tap","none");b=new NvdaGestureBindings(b.json());
        assertEquals("none",b.action("3:tap"));b.reset();assertEquals("menu",b.action("3:tap"));
    }
    @Test public void malformedOrUnknownSavedMappingsCannotExecuteCode() {
        NvdaGestureBindings b=new NvdaGestureBindings("{\"version\":1,\"mappings\":{\"1:up\":\"exec:cmd\",\"9:tap\":\"exit\",\"1:down\":\"key:Ctrl+Z\"}}");
        assertEquals("up",b.action("1:up"));assertEquals("key:Ctrl+Z",b.action("1:down"));
        assertEquals("up",new NvdaGestureBindings("{bad").action("1:up"));
    }
    @Test public void manualAndGestureActionsUseTheSameKeyboardShortcuts() {
        assertEquals("alt+f4",NvdaShortcut.parse(NvdaGestureBindings.shortcutFor("close_window")).canonical());
        assertEquals("windows+d",NvdaShortcut.parse(NvdaGestureBindings.shortcutFor("desktop")).canonical());
        assertEquals("alt+shift+tab",NvdaShortcut.parse(NvdaGestureBindings.shortcutFor("alt_shift_tab")).canonical());
        assertEquals("control+c",NvdaShortcut.parse(NvdaGestureBindings.shortcutFor("copy")).canonical());
        assertEquals("control+shift+s",NvdaShortcut.parse(NvdaGestureBindings.shortcutFor("key:Ctrl+Shift+S")).canonical());
        assertNull(NvdaGestureBindings.shortcutFor("window"));
    }
}
