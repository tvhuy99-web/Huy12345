package com.winlator.accessibility;

import org.junit.Test;
import java.util.Arrays;
import static org.junit.Assert.*;

public class NvdaControllerRuntimeAssetsTest {
    @Test public void earlyAudioLoaderIsAlwaysInstalledBesideProbe() {
        java.util.List<String> assets=Arrays.asList(NvdaController.RUNTIME_DIAGNOSTIC_ASSETS);
        assertTrue(assets.contains("voice-trace-x86.dll"));
        assertTrue(assets.contains("game-probe-x86.exe"));
        assertTrue(assets.contains("game-audio-loader-x86.exe"));
    }
}
