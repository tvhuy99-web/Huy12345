package com.winlator.accessibility;

import java.util.*;

/** One key with optional modifiers. No scripts, commands or multi-step macros. */
public final class NvdaShortcut {
    public final List<String> modifiers;
    public final String key;
    private NvdaShortcut(List<String> modifiers,String key) {this.modifiers=Collections.unmodifiableList(modifiers);this.key=key;}
    private static final List<String> ORDER=Arrays.asList("control","alt","shift","windows");
    public static NvdaShortcut parse(String text) {
        if(text==null || text.length()>80)throw new IllegalArgumentException();
        String normalized=text.trim().toLowerCase(Locale.ROOT).replaceAll("\\s*\\+\\s*","+").replaceAll("\\s+","+");
        if(normalized.isEmpty() || normalized.startsWith("+") || normalized.endsWith("+"))throw new IllegalArgumentException();
        Set<String> mods=new HashSet<>();String key=null;
        for(String token:normalized.split("\\+",-1)) {
            String value=alias(token);
            if(ORDER.contains(value)) {if(!mods.add(value))throw new IllegalArgumentException();}
            else {if(key!=null || !isKey(value))throw new IllegalArgumentException();key=value;}
        }
        if(key==null) {if(mods.size()!=1)throw new IllegalArgumentException();key=mods.iterator().next();mods.clear();}
        List<String> ordered=new ArrayList<>();for(String m:ORDER)if(mods.contains(m))ordered.add(m);
        return new NvdaShortcut(ordered,key);
    }
    private static String alias(String value) {
        switch(value) {
            case "ctrl":case "ctl":return "control";
            case "win":case "super":return "windows";
            case "esc":return "escape";
            case "return":return "enter";
            case "pgup":case "prior":return "pageup";
            case "pgdn":case "next":return "pagedown";
            case "del":return "delete";
            case "bksp":return "backspace";
            case "ins":return "insert";
            case "spacebar":return "space";
            default:return value;
        }
    }
    private static boolean isKey(String key) {
        return key.matches("[a-z0-9]|f([1-9]|1[0-2])") || Arrays.asList("up","down","left","right","enter","escape","tab","space",
            "home","end","pageup","pagedown","insert","delete","backspace","minus","equal","comma","period","slash","backslash","semicolon","apostrophe","bracketleft","bracketright").contains(key);
    }
    public String canonical() {return (modifiers.isEmpty()?"":String.join("+",modifiers)+"+")+key;}
    public String display() {
        List<String> values=new ArrayList<>(modifiers);values.add(key);
        for(int i=0;i<values.size();i++) {String value=values.get(i);values.set(i,value.equals("control")?"Ctrl":value.equals("windows")?"Windows":value.length()==1||value.matches("f\\d+")?value.toUpperCase(Locale.ROOT):Character.toUpperCase(value.charAt(0))+value.substring(1));}
        return String.join("+",values);
    }
    public NvdaShortcut withModifiers(Collection<String> held) {
        Set<String> all=new HashSet<>(modifiers);all.addAll(held);
        List<String> ordered=new ArrayList<>();for(String m:ORDER)if(all.contains(m) && !m.equals(key))ordered.add(m);
        return new NvdaShortcut(ordered,key);
    }
}
