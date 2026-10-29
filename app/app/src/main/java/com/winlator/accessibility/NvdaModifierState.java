package com.winlator.accessibility;

import java.util.*;

/** Logical one-shot modifiers; no physical key stays down while choosing a key. */
public final class NvdaModifierState {
    public enum Effect { HELD, RELEASED, PRESS_ONCE }
    private final Set<String> held=new LinkedHashSet<>();
    private String previous="";private long previousTime=-1;
    public Effect toggle(String modifier,long time) {
        if(!Arrays.asList("control","windows","alt","shift").contains(modifier))throw new IllegalArgumentException();
        if(held.contains(modifier)) {
            held.remove(modifier);
            boolean twice=previous.equals(modifier) && time>=previousTime && time-previousTime<=650;
            previous="";previousTime=-1;
            return twice?Effect.PRESS_ONCE:Effect.RELEASED;
        }
        held.add(modifier);previous=modifier;previousTime=time;return Effect.HELD;
    }
    public NvdaShortcut consume(NvdaShortcut shortcut) {
        NvdaShortcut result=shortcut.withModifiers(held);clear();return result;
    }
    public void interruptSequence() {previous="";previousTime=-1;}
    public void clear() {held.clear();interruptSequence();}
    public boolean isHeld() {return !held.isEmpty();}
}
