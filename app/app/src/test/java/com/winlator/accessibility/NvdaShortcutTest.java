package com.winlator.accessibility;
import org.junit.Test;
import java.util.*;
import static org.junit.Assert.*;
public class NvdaShortcutTest {
    @Test public void normalizesHumanSpellingAndModifierOrder() {
        assertEquals("control+c",NvdaShortcut.parse("ctrl c").canonical());
        assertEquals("control+shift+f12",NvdaShortcut.parse("Shift + CTRL + F12").canonical());
        assertEquals("Windows+D",NvdaShortcut.parse("win+d").display());
    }
    @Test public void allNamedKeysAndStandaloneModifiersAreSupported() {
        for(String key:new String[]{"Ctrl","Windows","Alt","Shift","Escape","Tab","PageUp","PageDown","Backspace","Delete","0","F1","F12"})assertFalse(NvdaShortcut.parse(key).canonical().isEmpty());
    }
    @Test public void rejectsScriptsMultipleKeysAndInvalidFunctionKeys() {
        for(String text:new String[]{"","Ctrl++C","ctrl+ctrl+c","Ctrl+C+V","F13","rm -rf","Ctrl+;","C;D","Windows+","Alt+Shift"}) {
            try{NvdaShortcut.parse(text);fail(text);}catch(IllegalArgumentException expected){}
        }
    }
    @Test public void heldModifiersMergeWithoutDuplicates() {
        assertEquals("control+shift+c",NvdaShortcut.parse("Ctrl+C").withModifiers(Arrays.asList("control","shift")).canonical());
    }
}
