package com.winlator.widget;

import android.content.Context;
import android.content.res.TypedArray;
import android.util.AttributeSet;
import android.view.LayoutInflater;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import com.winlator.accessibility.AccessibilitySupport;
import android.view.View;
import android.widget.EditText;
import android.widget.FrameLayout;

import com.winlator.R;
import com.winlator.math.Mathf;

public class NumberPicker extends FrameLayout implements View.OnClickListener {
    private int value = 0;
    private int minValue = 0;
    private int maxValue = 100;
    private int step = 1;
    private final EditText editText;
    private OnValueChangeListener onValueChangeListener;

    public interface OnValueChangeListener {
        void onValueChange(NumberPicker numberPicker, int value);
    }

    public NumberPicker(Context context) {
        this(context, null);
    }

    public NumberPicker(Context context, AttributeSet attrs) {
        this(context, attrs, 0);
    }

    public NumberPicker(Context context, AttributeSet attrs, int defStyleAttr) {
        super(context, attrs, defStyleAttr);

        LayoutInflater.from(context).inflate(R.layout.number_picker, this, true);
        editText = findViewById(R.id.EditText);
        setFocusable(true);
        setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
        for (int i = 0; i < getChildCount(); i++) getChildAt(i).setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        findViewById(R.id.BTDecrement).setOnClickListener(this);
        findViewById(R.id.BTIncrement).setOnClickListener(this);

        if (attrs != null) {
            TypedArray ta = context.obtainStyledAttributes(attrs, R.styleable.NumberPicker);
            minValue = ta.getInt(R.styleable.NumberPicker_minValue, minValue);
            maxValue = ta.getInt(R.styleable.NumberPicker_maxValue, maxValue);
            setStep(ta.getInt(R.styleable.NumberPicker_step, step));
            int value = ta.getInt(R.styleable.NumberPicker_value, 0);
            ta.recycle();
            setValue(value);
        }
        else setStep(step);
    }

    public void setValue(int value) {
        this.value = Mathf.clamp(value, minValue, maxValue);
        editText.setText(String.valueOf(this.value));
    }

    public int getValue() {
        return value;
    }

    public int getMinValue() {
        return minValue;
    }

    public void setMinValue(int minValue) {
        this.minValue = minValue;
    }

    public int getMaxValue() {
        return maxValue;
    }

    public void setMaxValue(int maxValue) {
        this.maxValue = maxValue;
    }

    public void increment() {
        setValue(value+step);
    }

    public void decrement() {
        setValue(value-step);
    }

    public int getStep() {
        return step;
    }

    public void setStep(int step) {
        this.step = step;
    }

    public OnValueChangeListener getOnValueChangeListener() {
        return onValueChangeListener;
    }

    public void setOnValueChangeListener(OnValueChangeListener onValueChangeListener) {
        this.onValueChangeListener = onValueChangeListener;
    }

    private void onButtonClick(View v) {
        if (!isEnabled()) return;

        int old = value;
        int id = v.getId();
        if (id == R.id.BTIncrement) {
            increment();
        }
        else if (id == R.id.BTDecrement) {
            decrement();
        }
        if (onValueChangeListener != null && old != value) {
            onValueChangeListener.onValueChange(NumberPicker.this, value);
        }
    }

    @Override
    public void onClick(View view) {
        int old = value;
        onButtonClick(view);
        if (old != value) sendAccessibilityEvent(AccessibilityEvent.TYPE_VIEW_SELECTED);
    }

    @Override
    public CharSequence getAccessibilityClassName() { return android.widget.SeekBar.class.getName(); }

    @Override
    public void onInitializeAccessibilityNodeInfo(AccessibilityNodeInfo info) {
        super.onInitializeAccessibilityNodeInfo(info);
        AccessibilitySupport.range(info, minValue, maxValue, value, isEnabled());
        info.setText(String.valueOf(value));
    }

    @Override
    public void onPopulateAccessibilityEvent(AccessibilityEvent event) {
        super.onPopulateAccessibilityEvent(event);
        event.getText().add(String.valueOf(value));
    }

    @Override
    public boolean performAccessibilityAction(int action, Bundle args) {
        Float next = AccessibilitySupport.requestedValue(action, args, minValue, maxValue, value, step);
        if (next == null) return super.performAccessibilityAction(action, args);
        if (!isEnabled()) return false;
        int old = value;
        setValue(Math.round(next));
        if (old == value) return false;
        if (onValueChangeListener != null) onValueChangeListener.onValueChange(this, value);
        sendAccessibilityEvent(AccessibilityEvent.TYPE_VIEW_SELECTED);
        return true;
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_DPAD_RIGHT || keyCode == KeyEvent.KEYCODE_PLUS)
            return performAccessibilityAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD, null);
        if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT || keyCode == KeyEvent.KEYCODE_MINUS)
            return performAccessibilityAction(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD, null);
        return super.onKeyDown(keyCode, event);
    }
}
