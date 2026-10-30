package com.winlator.accessibility;

import android.app.*;
import android.os.Looper;
import android.widget.*;
import java.util.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import org.robolectric.shadows.ShadowAlertDialog;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28) @LooperMode(LooperMode.Mode.PAUSED)
public class NvdaGestureActionDialogTest {
    private static class Output implements NvdaGestureActionDialog.Executor {
        final List<String> actions=new ArrayList<>(),shortcuts=new ArrayList<>(),texts=new ArrayList<>();
        final NvdaModifierState modifiers=new NvdaModifierState();int exits,clears;
        public void performManual(String action,NvdaGestureActionDialog.Presentation ui) {
            actions.add(action);
            if(action.startsWith("hold_"))modifiers.toggle(action.substring(5).replace("ctrl","control"),0);
            else if(action.equals("function_keys"))ui.keys(true);
            else if(action.equals("digit_keys"))ui.keys(false);
            else if(action.equals("keyboard"))ui.keyboard();
            else if(action.equals("menu"))ui.menu();
            else if(action.equals("exit"))ui.confirmExit(()->exits++);
            else {String key=NvdaGestureBindings.shortcutFor(action);if(key!=null)sendManualShortcut(key);}
        }
        public boolean sendManualShortcut(String value) {
            try {shortcuts.add(modifiers.consume(NvdaShortcut.parse(value)).canonical());return true;}
            catch(IllegalArgumentException e) {return false;}
        }
        public boolean sendManualText(String text) {texts.add(text);return !text.isEmpty();}
        public void clearManualModifiers() {clears++;modifiers.clear();}
        public void returnToWindows() {clearManualModifiers();}
    }
    private Activity activity;
    private Output output;
    private NvdaGestureActionDialog panel;
    private AlertDialog root;
    private void idle() {shadowOf(Looper.getMainLooper()).idle();}
    @Before public void open() {
        activity=Robolectric.buildActivity(Activity.class).setup().get();output=new Output();
        panel=new NvdaGestureActionDialog(activity,output);panel.show();idle();root=ShadowAlertDialog.getLatestAlertDialog();
    }
    @After public void close() {panel.close();idle();activity.finish();}
    private void choose(String action) {
        ListView list=root.findViewById(android.R.id.list);String label=NvdaGestureBindings.actionLabel(action);
        for(int i=0;i<list.getAdapter().getCount();i++)if(label.equals(list.getAdapter().getItem(i))) {
            list.performItemClick(null,i,i);idle();return;
        }
        fail("Missing manual action "+action);
    }
    @Test public void allAssignedFunctionsAreAvailableAndWindowsDUsesTheSharedShortcut() {
        ListView list=root.findViewById(android.R.id.list);
        assertEquals(NvdaGestureBindings.ACTIONS.length-1,list.getAdapter().getCount());
        choose("desktop");assertEquals(List.of("desktop"),output.actions);
        assertEquals(List.of("windows+d"),output.shortcuts);assertTrue(root.isShowing());
    }
    @Test public void customEditorPreservesTheHeldCtrlUntilTheNextKeyIsSent() {
        choose("hold_ctrl");assertTrue(output.modifiers.isHeld());
        root.getButton(AlertDialog.BUTTON_NEUTRAL).performClick();idle();assertTrue(root.isShowing());
        assertTrue(output.modifiers.isHeld());AlertDialog editor=ShadowAlertDialog.getLatestAlertDialog();
        ((EditText)editor.findViewById(android.R.id.edit)).setText("c");
        editor.getButton(AlertDialog.BUTTON_POSITIVE).performClick();idle();
        assertEquals(List.of("control+c"),output.shortcuts);assertTrue(root.isShowing());
        assertFalse(output.modifiers.isHeld());
    }
    @Test public void gameDiagnosticsAreManualActionsRatherThanGuessedKeyboardShortcuts() {
        choose("game_show");choose("game_voice_enable");choose("game_voice_restore");choose("game_startup_fix");choose("game_startup_restore");
        assertEquals(List.of("game_show","game_voice_enable","game_voice_restore","game_startup_fix","game_startup_restore"),output.actions);
        assertTrue(output.shortcuts.isEmpty());assertTrue(root.isShowing());
        assertArrayEquals(new String[]{"game_startup_fix","game_voice_enable","game_show","game_inspect","game_voice_restore","game_startup_restore"},NvdaTouchController.menuItems("game_tools"));
    }
    @Test public void invalidCustomShortcutStaysEditableAndClosingClearsAllModifiers() {
        choose("hold_ctrl");root.getButton(AlertDialog.BUTTON_NEUTRAL).performClick();idle();
        AlertDialog editor=ShadowAlertDialog.getLatestAlertDialog();EditText input=editor.findViewById(android.R.id.edit);
        input.setText("Ctrl+C+V");editor.getButton(AlertDialog.BUTTON_POSITIVE).performClick();idle();
        assertTrue(editor.isShowing());assertNotNull(input.getError());assertTrue(output.shortcuts.isEmpty());
        panel.close();idle();assertFalse(editor.isShowing());assertFalse(root.isShowing());assertFalse(output.modifiers.isHeld());
    }
    @Test public void functionAndDigitPickersSendF12AndNineThroughTheSameExecutor() {
        choose("function_keys");AlertDialog keys=ShadowAlertDialog.getLatestAlertDialog();
        assertEquals(12,keys.getListView().getAdapter().getCount());keys.getListView().performItemClick(null,11,11);idle();
        choose("digit_keys");keys=ShadowAlertDialog.getLatestAlertDialog();
        assertEquals(10,keys.getListView().getAdapter().getCount());keys.getListView().performItemClick(null,9,9);idle();
        assertEquals(List.of("f12","9"),output.shortcuts);assertTrue(root.isShowing());
    }
    @Test public void keyboardSendsUnicodeTextRatherThanParsingItAsAKeyShortcut() {
        choose("keyboard");AlertDialog editor=ShadowAlertDialog.getLatestAlertDialog();
        ((EditText)editor.findViewById(android.R.id.edit)).setText("Tiếng Việt");
        editor.getButton(AlertDialog.BUTTON_POSITIVE).performClick();idle();
        assertEquals(List.of("Tiếng Việt"),output.texts);assertTrue(output.shortcuts.isEmpty());
    }
    @Test public void manualMenuUsesTheSameWindowGroupAndDesktopAction() {
        choose("menu");AlertDialog menu=ShadowAlertDialog.getLatestAlertDialog();
        String[] groups=NvdaTouchController.menuItems("");int windows=Arrays.asList(groups).indexOf("windows_group");
        menu.getListView().performItemClick(null,windows,windows);idle();menu=ShadowAlertDialog.getLatestAlertDialog();
        int desktop=Arrays.asList(NvdaTouchController.menuItems("windows_group")).indexOf("desktop");
        menu.getListView().performItemClick(null,desktop,desktop);idle();
        assertEquals(List.of("menu","desktop"),output.actions);assertEquals(List.of("windows+d"),output.shortcuts);
    }
    @Test public void exitingTheEnvironmentRequiresTheSeparateConfirmationButton() {
        choose("exit");assertEquals(0,output.exits);AlertDialog confirm=ShadowAlertDialog.getLatestAlertDialog();
        confirm.getButton(AlertDialog.BUTTON_POSITIVE).performClick();idle();assertEquals(1,output.exits);
    }
}
