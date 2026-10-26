package com.winlator.accessibility;

import android.app.AlertDialog;
import android.app.Dialog;
import android.os.Bundle;
import android.text.InputFilter;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import androidx.core.view.ViewCompat;
import com.winlator.R;
import com.winlator.XServerDisplayActivity;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/** Accessible Android projection of REAL controls read from the running Wine guest. */
public final class GuestAccessibilityDialog implements GuestBridge.Listener, AutoCloseable {
    private final XServerDisplayActivity activity;
    private final GuestBridge bridge;
    private Dialog dialog;
    private TextView status, heading, explanation;
    private LinearLayout items;
    private GuestSnapshot snapshot;
    private View returnFocus;
    private final Map<String, TextView> rows = new HashMap<>();
    private long displayedRevision = -1;

    public GuestAccessibilityDialog(XServerDisplayActivity activity) {
        this.activity = activity; bridge = new GuestBridge(activity, this);
    }
    private int dp(int value) { return Math.round(value * activity.getResources().getDisplayMetrics().density); }
    private LinearLayout column() {
        LinearLayout view = new LinearLayout(activity); view.setOrientation(LinearLayout.VERTICAL); return view;
    }
    private Button button(LinearLayout parent, int label, Runnable action) {
        Button button = new Button(activity); button.setText(label); button.setMinHeight(dp(48));
        parent.addView(button, new LinearLayout.LayoutParams(-1, -2));
        button.setOnClickListener(v -> action.run()); return button;
    }
    public void show() {
        if (activity.getContainer() == null || activity.isFinishing()) return;
        if (dialog != null && dialog.isShowing()) return;
        returnFocus = AccessibilitySupport.captureFocus(activity);
        displayedRevision = -1; rows.clear();
        dialog = new Dialog(activity); dialog.setTitle(R.string.guest_title);
        LinearLayout root = column(); root.setPadding(dp(12), dp(8), dp(12), dp(8));
        ScrollView scroll = new ScrollView(activity); scroll.setFillViewport(true);
        LinearLayout content = column(); scroll.addView(content);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        heading = new TextView(activity); heading.setTextSize(20); ViewCompat.setAccessibilityHeading(heading, true);
        content.addView(heading);
        status = new TextView(activity); status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        status.setPadding(0, dp(8), 0, dp(8)); content.addView(status);
        button(content, R.string.guest_windows, this::chooseWindow);
        button(content, R.string.guest_refresh, () -> send("snapshot"));
        button(content, R.string.guest_keys, this::chooseKey);
        explanation = new TextView(activity); explanation.setText(R.string.guest_instructions);
        content.addView(explanation);
        items = column(); content.addView(items);
        button(content, R.string.guest_test, () -> send("test"));
        button(content, R.string.guest_reconnect, () -> {
            snapshot = null; displayedRevision = -1; rows.clear(); items.removeAllViews();
            bridge.close(); bridge.start(); bridge.setPolling(true);
        });
        button(root, R.string.guest_close, () -> dialog.dismiss());
        dialog.setContentView(root);
        dialog.setOnDismissListener(d -> {
            bridge.setPolling(false); AccessibilitySupport.restoreFocus(returnFocus);
        });
        dialog.show();
        Window window = dialog.getWindow();
        if (window != null) window.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
        ViewCompat.setAccessibilityPaneTitle(root, activity.getString(R.string.guest_title));
        heading.setText(R.string.guest_title); status.setText(R.string.guest_connecting);
        if (snapshot != null) onSnapshot(snapshot);
        bridge.setPolling(true); bridge.start();
        AccessibilitySupport.focusDialog(root);
    }
    private void send(String command) {
        if (!bridge.command(command)) onStatus(R.string.guest_busy);
    }
    @Override public void onStatus(int message) {
        if (status != null) status.setText(message);
        if (message == R.string.guest_connecting || message == R.string.guest_disconnected) {
            snapshot = null; displayedRevision = -1; rows.clear();
            if (items != null) items.removeAllViews();
        }
    }
    @Override public void onSnapshot(GuestSnapshot next) {
        snapshot = next;
        if (dialog == null || !dialog.isShowing()) return;
        if (next.result != 0) {
            int[] resultStrings = {R.string.guest_ready, R.string.guest_action_done,
                    R.string.guest_action_failed, R.string.guest_stale, R.string.guest_unsupported};
            status.setText(resultStrings[next.result]);
        } else if (displayedRevision == -1) status.setText(R.string.guest_ready);
        if (displayedRevision == next.revision) return;
        displayedRevision = next.revision;
        String title = next.title.isEmpty() ? activity.getString(R.string.guest_no_window) : next.title;
        if (!title.contentEquals(heading.getText())) heading.setText(title);
        explanation.setText(next.nodes.isEmpty() ? R.string.guest_empty : next.limited ? R.string.guest_limited : R.string.guest_instructions);
        Set<String> present = new HashSet<>();
        int index = 0;
        for (GuestSnapshot.Node node : next.nodes) {
            String key = node.id + ":" + node.role + ":" + node.source + ":" + node.name;
            present.add(key);
            TextView row = rows.get(key);
            if (row == null) {
                row = node.click || node.edit ? new Button(activity) : new TextView(activity);
                row.setMinHeight(dp(48)); row.setPadding(dp(8), dp(12), dp(8), dp(12));
                row.setFocusable(true); row.setTextSize(16); rows.put(key, row);
                final TextView item = row;
                row.setOnClickListener(v -> operate((GuestSnapshot.Node)item.getTag()));
                row.setClickable(node.click || node.edit);
                row.setOnLongClickListener(v -> { focus((GuestSnapshot.Node)item.getTag()); return true; });
                row.setAccessibilityDelegate(new View.AccessibilityDelegate() {
                    @Override public void onInitializeAccessibilityNodeInfo(View host, AccessibilityNodeInfo info) {
                        super.onInitializeAccessibilityNodeInfo(host, info);
                        GuestSnapshot.Node current = (GuestSnapshot.Node)host.getTag();
                        if (current == null) return;
                        if (current.role == 44 || current.role == 45) {
                            info.setClassName(current.role == 44 ? android.widget.CheckBox.class.getName() : android.widget.RadioButton.class.getName());
                            info.setCheckable(true); info.setChecked(current.checked());
                        }
                        info.setSelected(current.selected());
                        info.addAction(new AccessibilityNodeInfo.AccessibilityAction(
                                AccessibilityNodeInfo.ACTION_LONG_CLICK, activity.getString(R.string.guest_focus)));
                    }
                });
            }
            row.setTag(node); row.setEnabled(node.enabled());
            String summary = summary(node);
            if (!summary.contentEquals(row.getText())) row.setText(summary);
            int current = items.indexOfChild(row);
            if (current != index) {
                if (current >= 0) items.removeView(row);
                items.addView(row, Math.min(index, items.getChildCount()), new LinearLayout.LayoutParams(-1, -2));
            }
            index++;
        }
        boolean lostFocus = false;
        for (String key : new HashSet<>(rows.keySet())) if (!present.contains(key)) {
            TextView row = rows.remove(key); lostFocus |= row.isAccessibilityFocused(); items.removeView(row);
        }
        if (lostFocus) AccessibilitySupport.restoreFocus(heading);
    }
    private String summary(GuestSnapshot.Node node) {
        String name = node.name.replace("&&", "\0").replace("&", "").replace('\0', '&');
        if (name.trim().isEmpty()) name = activity.getString(R.string.guest_unnamed);
        String label = name + ", " + activity.getString(roleString(node.role));
        if (node.password) label += ", " + activity.getString(R.string.guest_password);
        else if (!node.value.isEmpty() && !node.value.equals(node.name)) label += ": " + node.value;
        if (node.focused()) label += ", " + activity.getString(R.string.guest_focused);
        return label;
    }
    private static int roleString(int role) {
        switch (role) {
            case 43: return R.string.guest_role_button;
            case 44: return R.string.guest_role_checkbox;
            case 45: return R.string.guest_role_radio;
            case 42: return R.string.guest_role_edit;
            case 46: return R.string.guest_role_combo;
            case 33: return R.string.guest_role_list;
            case 34: return R.string.guest_role_item;
            case 35: return R.string.guest_role_tree;
            case 12: return R.string.guest_role_menu;
            case 48: return R.string.guest_role_progress;
            default: return R.string.guest_role_text;
        }
    }
    private void focus(GuestSnapshot.Node node) {
        if (snapshot != null && node.enabled()) send(GuestProtocol.action(snapshot.revision, node.id, "focus", ""));
    }
    private void operate(GuestSnapshot.Node node) {
        if (snapshot == null || !node.enabled()) return;
        if (node.edit) { edit(node); return; }
        if (node.click) send(GuestProtocol.action(snapshot.revision, node.id, "click", ""));
    }
    private void edit(GuestSnapshot.Node node) {
        // Capture this revision now; submitting after the guest changes must be rejected.
        long revision = snapshot.revision;
        EditText input = new EditText(activity); input.setSingleLine(false);
        input.setHint(node.name.isEmpty() ? activity.getString(R.string.guest_role_edit) : node.name);
        input.setContentDescription(input.getHint()); input.setText(node.value);
        input.setFilters(new InputFilter[]{new InputFilter.LengthFilter(GuestSnapshot.MAX_TEXT)});
        AlertDialog editor = new AlertDialog.Builder(activity).setTitle(R.string.guest_edit_title).setView(input)
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(R.string.guest_apply, (d, which) -> {
                    try { send(GuestProtocol.action(revision, node.id, "edit", input.getText().toString())); }
                    catch (IllegalArgumentException invalid) { onStatus(R.string.guest_unsupported); }
                }).create();
        editor.setOnDismissListener(d -> bridge.setPolling(true));
        bridge.setPolling(false); editor.show(); input.requestFocus();
    }
    private void chooseWindow() {
        if (snapshot == null || snapshot.windows.isEmpty()) { onStatus(R.string.guest_no_window); return; }
        GuestSnapshot current = snapshot;
        String[] titles = new String[current.windows.size()];
        for (int i = 0; i < titles.length; i++) titles[i] = current.windows.get(i).name;
        new AlertDialog.Builder(activity).setTitle(R.string.guest_windows).setItems(titles,
                (d, index) -> send("window\t" + current.windows.get(index).id))
                .setNegativeButton(android.R.string.cancel, null).show();
    }
    private void chooseKey() {
        if (snapshot == null) return;
        String[] commands = {"tab", "backtab", "enter", "escape", "up", "down", "left", "right", "space"};
        String[] names = activity.getResources().getStringArray(R.array.guest_key_names);
        new AlertDialog.Builder(activity).setTitle(R.string.guest_keys).setItems(names, (d, i) -> {
            if (snapshot != null) send("key\t" + snapshot.revision + "\t" + commands[i]);
        }).setNegativeButton(android.R.string.cancel, null).show();
    }
    public void setActive(boolean active) { bridge.setPolling(active && dialog != null && dialog.isShowing()); }
    @Override public void close() {
        bridge.close(); if (dialog != null && dialog.isShowing()) dialog.dismiss(); rows.clear();
    }
}
