package com.winlator.accessibility;

import android.app.AlertDialog;
import android.content.Context;
import android.text.InputFilter;
import android.text.InputType;
import android.view.WindowManager;
import android.widget.*;
import com.winlator.R;
import java.util.*;

/** Native, TalkBack-accessible controls which invoke the same actions as raw gestures. */
public final class NvdaGestureActionDialog implements AutoCloseable {
    public interface Executor {
        void performManual(String action,Presentation presentation);
        boolean sendManualShortcut(String shortcut);
        boolean sendManualText(String text);
        void clearManualModifiers();
        void returnToWindows();
    }
    public interface Presentation {
        void menu();
        void keyboard();
        void keys(boolean functions);
        void confirmExit(Runnable exit);
    }
    private final Context context;
    private final Executor executor;
    private AlertDialog root;
    private final List<AlertDialog> dialogs=new ArrayList<>();
    private final Presentation presentation=new Presentation() {
        public void menu() {NvdaGestureActionDialog.this.menu();}
        public void keyboard() {NvdaGestureActionDialog.this.keyboard();}
        public void keys(boolean functions) {NvdaGestureActionDialog.this.keys(functions);}
        public void confirmExit(Runnable exit) {NvdaGestureActionDialog.this.confirmExit(exit);}
    };
    public NvdaGestureActionDialog(Context context,Executor executor) {this.context=context;this.executor=executor;}
    public void show() {
        List<String> actions=new ArrayList<>(Arrays.asList(NvdaGestureBindings.ACTIONS));actions.remove("none");
        ListView list=new ListView(context);list.setId(android.R.id.list);
        List<String> labels=new ArrayList<>();for(String action:actions)labels.add(NvdaGestureBindings.actionLabel(action));
        list.setAdapter(new ArrayAdapter<>(context,android.R.layout.simple_list_item_1,labels));
        list.setOnItemClickListener((parent,view,position,id)->executor.performManual(actions.get(position),presentation));
        root=new AlertDialog.Builder(context).setTitle(R.string.nvda_gesture_actions).setView(list)
            .setNeutralButton(R.string.nvda_gesture_custom,null).setNegativeButton(R.string.nvda_gesture_close,null).create();
        root.setOnShowListener(d->root.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v->editor(false)));
        display(root,true);
    }
    private void editor(boolean text) {
        EditText input=new EditText(context);input.setId(android.R.id.edit);input.setSingleLine(!text);
        input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        input.setFilters(new InputFilter[]{new InputFilter.LengthFilter(text?256:80)});
        if(!text)input.setHint("Ctrl+C");
        FrameLayout box=new FrameLayout(context);int pad=Math.round(20*context.getResources().getDisplayMetrics().density);
        box.setPadding(pad,0,pad,0);box.addView(input,new FrameLayout.LayoutParams(-1,-2));
        AlertDialog dialog=new AlertDialog.Builder(context).setTitle(text?R.string.nvda_keyboard:R.string.nvda_gesture_custom)
            .setView(box).setPositiveButton(R.string.nvda_gesture_send,null).setNegativeButton(android.R.string.cancel,null).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            boolean sent=text?executor.sendManualText(input.getText().toString()):executor.sendManualShortcut(input.getText().toString());
            if(sent)dialog.dismiss();else input.setError(context.getString(R.string.nvda_gesture_invalid_shortcut));
        }));
        dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE);
        display(dialog,false);input.requestFocus();
    }
    public void keyboard() {editor(true);}
    public void keys(boolean functions) {
        String[] labels=new String[functions?12:10];
        for(int i=0;i<labels.length;i++)labels[i]=functions?"F"+(i+1):String.valueOf(i);
        AlertDialog dialog=new AlertDialog.Builder(context).setTitle(functions?R.string.nvda_function_keys:R.string.nvda_number_keys)
            .setItems(labels,(d,i)->executor.sendManualShortcut(labels[i])).setNegativeButton(android.R.string.cancel,null).create();
        display(dialog,false);
    }
    public void confirmExit(Runnable exit) {
        AlertDialog dialog=new AlertDialog.Builder(context).setMessage(R.string.nvda_exit_environment)
            .setPositiveButton(R.string.nvda_exit_environment,(d,w)->exit.run()).setNegativeButton(android.R.string.cancel,null).create();
        display(dialog,false);
    }
    public void menu() {menu("");}
    private void menu(String group) {
        String[] actions=NvdaTouchController.menuItems(group),labels=new String[actions.length];
        for(int i=0;i<labels.length;i++)labels[i]=NvdaTouchController.actionLabel(actions[i]);
        AlertDialog dialog=new AlertDialog.Builder(context).setTitle(group.isEmpty()?context.getString(R.string.nvda_control_menu):NvdaTouchController.actionLabel(group))
            .setItems(labels,(choice,i)->{
                String action=actions[i];
                if(NvdaTouchController.isMenuGroup(action))menu(action);
                else if(action.equals("close"))executor.returnToWindows();
                else executor.performManual(action,presentation);
            }).setNegativeButton(android.R.string.cancel,null).create();
        display(dialog,false);
    }
    private void display(AlertDialog dialog,boolean main) {
        dialogs.add(dialog);
        dialog.setOnDismissListener(d->{dialogs.remove(dialog);if(main)executor.clearManualModifiers();});
        dialog.show();
    }
    public boolean isShowing() {return root!=null&&root.isShowing();}
    @Override public void close() {
        List<AlertDialog> open=new ArrayList<>(dialogs);Collections.reverse(open);
        for(AlertDialog dialog:open)dialog.dismiss();
        dialogs.clear();executor.clearManualModifiers();
    }
}
