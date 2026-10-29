package com.winlator.accessibility;

import android.app.AlertDialog;
import android.content.Context;
import android.text.InputType;
import android.widget.*;
import com.winlator.R;
import com.winlator.container.Container;
import java.util.*;

/** Compact Android settings, accessible with TalkBack before entering the environment. */
public final class NvdaGestureSettingsDialog {
    private final Context context;
    private final Container container;
    private final NvdaGestureBindings bindings;
    private final List<String> ids=NvdaGestureBindings.gestures();
    private ArrayAdapter<String> adapter;
    public NvdaGestureSettingsDialog(Context context,Container container) {
        this.context=context;this.container=container;bindings=new NvdaGestureBindings(container.getExtra(NvdaGestureBindings.EXTRA));
    }
    public void show() {
        ListView list=new ListView(context);list.setId(android.R.id.list);adapter=new ArrayAdapter<>(context,android.R.layout.simple_list_item_1,new ArrayList<>());
        list.setAdapter(adapter);refresh();list.setOnItemClickListener((parent,view,position,id)->choose(ids.get(position)));
        AlertDialog dialog=new AlertDialog.Builder(context).setTitle(R.string.gestures).setView(list)
            .setNegativeButton(R.string.nvda_gesture_close,null).setNeutralButton(R.string.nvda_gesture_reset,null).create();
        dialog.setOnShowListener(v->dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(b->
            new AlertDialog.Builder(context).setMessage(R.string.nvda_gesture_reset_question)
                .setPositiveButton(android.R.string.ok,(d,w)->{bindings.reset();save();})
                .setNegativeButton(android.R.string.cancel,null).show()));
        dialog.show();
    }
    private void refresh() {adapter.clear();for(String id:ids)adapter.add(NvdaGestureBindings.gestureLabel(id)+"\n"+NvdaGestureBindings.actionLabel(bindings.action(id)));adapter.notifyDataSetChanged();}
    private void save() {container.putExtra(NvdaGestureBindings.EXTRA,bindings.json());container.saveData();refresh();}
    private void choose(String id) {
        String[] values=NvdaGestureBindings.ACTIONS;String[] names=new String[values.length];int selected=-1;
        for(int i=0;i<values.length;i++) {names[i]=NvdaGestureBindings.actionLabel(values[i]);if(bindings.action(id).equals(values[i]))selected=i;}
        new AlertDialog.Builder(context).setTitle(NvdaGestureBindings.gestureLabel(id))
            .setSingleChoiceItems(names,selected,(d,index)->{bindings.set(id,values[index]);save();d.dismiss();})
            .setNeutralButton(R.string.nvda_gesture_custom,(d,w)->custom(id))
            .setNegativeButton(android.R.string.cancel,null).show();
    }
    private void custom(String id) {
        EditText input=new EditText(context);input.setId(android.R.id.edit);input.setSingleLine(true);input.setHint("Ctrl+C");
        input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        String current=bindings.action(id);if(current.startsWith("key:"))input.setText(current.substring(4));
        FrameLayout box=new FrameLayout(context);int padding=Math.round(20*context.getResources().getDisplayMetrics().density);
        box.setPadding(padding,0,padding,0);box.addView(input,new FrameLayout.LayoutParams(-1,-2));
        AlertDialog dialog=new AlertDialog.Builder(context).setTitle(R.string.nvda_gesture_custom).setView(box)
            .setPositiveButton(R.string.nvda_gesture_save,null).setNegativeButton(android.R.string.cancel,null).create();
        dialog.setOnShowListener(v->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(b->{
            try {bindings.set(id,"key:"+NvdaShortcut.parse(input.getText().toString()).display());save();dialog.dismiss();}
            catch(IllegalArgumentException e) {input.setError(context.getString(R.string.nvda_gesture_invalid_shortcut));}
        }));dialog.show();input.requestFocus();
    }
}
