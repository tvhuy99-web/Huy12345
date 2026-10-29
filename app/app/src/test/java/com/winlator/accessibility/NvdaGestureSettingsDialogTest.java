package com.winlator.accessibility;
import android.app.*;
import android.os.Looper;
import android.widget.*;
import com.winlator.container.Container;
import com.winlator.core.FileUtils;
import org.json.JSONObject;
import org.junit.*;
import org.junit.rules.TemporaryFolder;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.LooperMode;
import org.robolectric.shadows.ShadowAlertDialog;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;
@RunWith(RobolectricTestRunner.class) @Config(sdk=28) @LooperMode(LooperMode.Mode.PAUSED)
public class NvdaGestureSettingsDialogTest {
    private void idle() {shadowOf(Looper.getMainLooper()).idle();}
    @Rule public TemporaryFolder temporary=new TemporaryFolder();
    @Test public void customCtrlCIsSavedAndReloadedForThisContainer() throws Exception {
        Activity activity=Robolectric.buildActivity(Activity.class).setup().get();
        Container container=new Container(1);container.setRootDir(temporary.newFolder());
        new NvdaGestureSettingsDialog(activity,container).show();idle();
        AlertDialog root=ShadowAlertDialog.getLatestAlertDialog();ListView list=root.findViewById(android.R.id.list);
        assertEquals(40,list.getAdapter().getCount());list.performItemClick(null,0,0);idle();
        ShadowAlertDialog.getLatestAlertDialog().getButton(AlertDialog.BUTTON_NEUTRAL).performClick();idle();
        AlertDialog custom=ShadowAlertDialog.getLatestAlertDialog();EditText input=custom.findViewById(android.R.id.edit);
        input.setText("ctrl c");custom.getButton(AlertDialog.BUTTON_POSITIVE).performClick();idle();
        assertEquals("key:Ctrl+C",new NvdaGestureBindings(container.getExtra(NvdaGestureBindings.EXTRA)).action("1:up"));
        Container reloaded=new Container(1);reloaded.setRootDir(container.getRootDir());reloaded.loadData(new JSONObject(FileUtils.readString(container.getConfigFile())));
        assertEquals("key:Ctrl+C",new NvdaGestureBindings(reloaded.getExtra(NvdaGestureBindings.EXTRA)).action("1:up"));
        assertEquals("up",new NvdaGestureBindings(new Container(2).getExtra(NvdaGestureBindings.EXTRA)).action("1:up"));
        root.dismiss();activity.finish();
    }
    @Test public void invalidRuleStaysInEditorWithoutChangingGesture() throws Exception {
        Activity activity=Robolectric.buildActivity(Activity.class).setup().get();Container container=new Container(3);container.setRootDir(temporary.newFolder());
        new NvdaGestureSettingsDialog(activity,container).show();idle();AlertDialog root=ShadowAlertDialog.getLatestAlertDialog();
        ((ListView)root.findViewById(android.R.id.list)).performItemClick(null,0,0);idle();
        ShadowAlertDialog.getLatestAlertDialog().getButton(AlertDialog.BUTTON_NEUTRAL).performClick();idle();AlertDialog custom=ShadowAlertDialog.getLatestAlertDialog();
        EditText input=custom.findViewById(android.R.id.edit);input.setText("Ctrl+C+V");custom.getButton(AlertDialog.BUTTON_POSITIVE).performClick();idle();
        assertTrue(custom.isShowing());assertNotNull(input.getError());assertEquals("up",new NvdaGestureBindings(container.getExtra(NvdaGestureBindings.EXTRA)).action("1:up"));
        custom.dismiss();root.dismiss();activity.finish();
    }
}
