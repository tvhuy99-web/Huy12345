package com.winlator;

import android.app.*;
import android.os.Bundle;
import com.winlator.accessibility.NvdaDiagnosticLog;

/** Starts diagnostics before the first screen, including sessions after returning from Wine. */
public final class WinlatorApplication extends Application {
    @Override public void onCreate() {
        super.onCreate();
        try {
            android.content.pm.PackageInfo info=getPackageManager().getPackageInfo(getPackageName(),0);
            NvdaDiagnosticLog.record("app.start","Winlator "+info.versionName+" ("+info.versionCode+")");
        }catch(Exception e) {NvdaDiagnosticLog.error("app.start",e);}
        registerActivityLifecycleCallbacks(new ActivityLifecycleCallbacks() {
            private void event(Activity activity,String state) {NvdaDiagnosticLog.record("android.lifecycle",activity.getClass().getSimpleName()+" "+state);}
            public void onActivityCreated(Activity a,Bundle state) {event(a,"created");}
            public void onActivityStarted(Activity a) {event(a,"started");}
            public void onActivityResumed(Activity a) {event(a,"resumed");}
            public void onActivityPaused(Activity a) {event(a,"paused");}
            public void onActivityStopped(Activity a) {event(a,"stopped");}
            public void onActivitySaveInstanceState(Activity a,Bundle state) {event(a,"saved");}
            public void onActivityDestroyed(Activity a) {event(a,"destroyed");}
        });
    }
}
