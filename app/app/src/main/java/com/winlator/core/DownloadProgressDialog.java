package com.winlator.core;

import com.winlator.accessibility.AccessibilitySupport;
import android.app.Activity;
import android.app.Dialog;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.TextView;

import com.google.android.material.progressindicator.CircularProgressIndicator;
import com.winlator.R;
import com.winlator.math.Mathf;

public class DownloadProgressDialog {
    private final Activity activity;
    private Dialog dialog;
    private View returnFocus;
    private String statusLabel;
    private int lastProgressBucket = -1;

    public DownloadProgressDialog(Activity activity) {
        this.activity = activity;
    }

    private void create() {
        if (dialog != null) return;
        dialog = new Dialog(activity, android.R.style.Theme_Translucent_NoTitleBar_Fullscreen);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        dialog.setCancelable(false);
        dialog.setCanceledOnTouchOutside(false);
        dialog.setContentView(R.layout.download_progress_dialog);

        Window window = dialog.getWindow();
        if (window != null) {
            window.clearFlags(WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE);
            window.clearFlags(WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE);
        }
    }

    public void show() {
        show(null);
    }

    public void show(int textResId) {
        show(textResId, null);
    }

    public void show(Runnable onCancelCallback) {
        show(0, onCancelCallback);
    }

    public void show(int textResId, final Runnable onCancelCallback) {
        if (isShowing()) return;
        close();
        if (dialog == null) create();

        statusLabel = activity.getString(textResId > 0 ? textResId : R.string.downloading_file);
        lastProgressBucket = -1;
        ((TextView)dialog.findViewById(R.id.TextView)).setText(statusLabel);
        dialog.findViewById(R.id.LLBottomBar).setVisibility(View.GONE);

        setProgress(0);
        if (onCancelCallback != null) {
            dialog.findViewById(R.id.BTCancel).setOnClickListener((v) -> onCancelCallback.run());
            dialog.findViewById(R.id.LLBottomBar).setVisibility(View.VISIBLE);
        }
        returnFocus = AccessibilitySupport.captureFocus(activity);
        dialog.show();
        AccessibilitySupport.focusDialog(dialog.findViewById(R.id.TextView));
    }

    public void setProgress(int progress) {
        if (dialog == null) return;
        final int value = Mathf.clamp(progress, 0, 100);
        activity.runOnUiThread(() -> {
            ((CircularProgressIndicator)dialog.findViewById(R.id.CircularProgressIndicator)).setProgress(value);
            ((TextView)dialog.findViewById(R.id.TVProgress)).setText(value + "%");
            int bucket = value / 10;
            if (bucket != lastProgressBucket) {
                lastProgressBucket = bucket;
                ((TextView)dialog.findViewById(R.id.TextView)).setText(activity.getString(R.string.a11y_progress, statusLabel, value));
            }
        });
    }

    public void close() {
        try {
            if (dialog != null) {
                boolean showing = dialog.isShowing();
                dialog.dismiss();
                if (showing) AccessibilitySupport.restoreFocus(returnFocus);
            }
        }
        catch (Exception e) {}
    }

    public void closeOnUiThread() {
        activity.runOnUiThread(this::close);
    }

    public boolean isShowing() {
        return dialog != null && dialog.isShowing();
    }
}
