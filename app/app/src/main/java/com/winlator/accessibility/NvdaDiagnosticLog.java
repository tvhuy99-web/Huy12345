package com.winlator.accessibility;

import java.text.SimpleDateFormat;
import java.util.*;

/** Shared, session-local history. The limit includes timestamps and exported metadata. */
public final class NvdaDiagnosticLog {
    public static final int MAX_CHARACTERS=500000;
    private static final NvdaDiagnosticLog INSTANCE=new NvdaDiagnosticLog();
    private final ArrayDeque<String> entries=new ArrayDeque<>();
    private final SimpleDateFormat clock=new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",Locale.ROOT);
    private int characters;private long sequence,removed;
    public NvdaDiagnosticLog() {clock.setTimeZone(TimeZone.getTimeZone("UTC"));}
    public static void record(String category,String details) {INSTANCE.append(category,details);}
    public static NvdaDiagnosticLog shared() {return INSTANCE;}
    public synchronized void append(String category,String details) {
        String value=String.valueOf(details).replace("\r","\\r").replace("\n","\\n");
        String kind=String.valueOf(category).replaceAll("[^a-zA-Z0-9_.-]","_");
        if(kind.length()>48)kind=kind.substring(0,48);
        for(int at=0;at<value.length()||at==0;) {
            int end=Math.min(value.length(),at+4000);
            if(end<value.length()&&Character.isHighSurrogate(value.charAt(end-1)))end--;
            String entry=clock.format(new Date())+" #"+(++sequence)+" ["+kind+"] "+value.substring(at,end)+"\n";
            entries.addLast(entry);characters+=entry.length();
            while(characters>MAX_CHARACTERS) {characters-=entries.removeFirst().length();removed++;}
            at=end;if(at==value.length())break;
        }
    }
    public synchronized String snapshot(String header) {
        String prefix=String.valueOf(header)+"\nGiới hạn: "+MAX_CHARACTERS+" ký tự; bản ghi cũ đã bỏ: "+removed+"\n";
        if(prefix.length()>8000)prefix=prefix.substring(0,7999)+"\n";
        StringBuilder result=new StringBuilder(prefix);
        int skip=characters+prefix.length()-MAX_CHARACTERS;
        for(String entry:entries) {if(skip>0) {skip-=entry.length();continue;}result.append(entry);}
        return result.toString();
    }
    public synchronized void clear() {entries.clear();characters=0;removed=0;}
    public static String action(String action,String text) {
        if("text".equals(action)||"message".equals(action))return action+"; nội dung đã che; ký tự="+(text==null?0:text.length());
        if("shortcut".equals(action))return action+"; "+shortcut(text);
        return action;
    }
    public static String shortcut(String text) {
        if(text==null)return "null";
        try {
            NvdaShortcut value=NvdaShortcut.parse(text);
            // Individual typed characters can otherwise reconstruct a password in the log.
            if((value.modifiers.isEmpty()||value.modifiers.equals(Collections.singletonList("shift")))&&value.key.matches("[a-z0-9]|space|minus|equal|comma|period|slash|backslash|semicolon|apostrophe|bracketleft|bracketright"))return "[phím nhập liệu đã che]";
            return value.canonical();
        }catch(Exception e) {return "[tổ hợp không hợp lệ]";}
    }
    public static void error(String category,Throwable error) {
        StringBuilder details=new StringBuilder(error.getClass().getSimpleName());
        // Messages/arguments may contain typed text or paths; locations identify the failure safely.
        int count=0;
        for(StackTraceElement frame:error.getStackTrace()) {
            if(!frame.getClassName().startsWith("com.winlator."))continue;
            details.append("; at=").append(frame.getClassName()).append('.').append(frame.getMethodName())
                .append(':').append(frame.getLineNumber());
            if(++count==8)break;
        }
        record(category,details.toString());
    }
}
