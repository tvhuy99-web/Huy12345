package com.winlator.core;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import android.content.Context;

import com.github.luben.zstd.ZstdInputStream;

import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.Arrays;

/** Verifies the runtime patch is pinned to the exact Wine binary bundled in the APK. */
@RunWith(RobolectricTestRunner.class)
public class WineLocaleBinaryPatchAssetTest {
    @Test public void bundledWineHasExpectedLocaleBranch() throws Exception {
        Context context = RuntimeEnvironment.getApplication();
        byte[] ntdll = null;
        try (InputStream asset = context.getAssets().open("rootfs.tzst");
             ZstdInputStream zstd = new ZstdInputStream(asset);
             TarArchiveInputStream tar = new TarArchiveInputStream(zstd)) {
            TarArchiveEntry entry;
            while ((entry = tar.getNextTarEntry()) != null) {
                String name = entry.getName();
                if ("./opt/wine/lib/wine/x86_64-unix/ntdll.so".equals(name)
                        || "opt/wine/lib/wine/x86_64-unix/ntdll.so".equals(name)) {
                    ByteArrayOutputStream output = new ByteArrayOutputStream((int)entry.getSize());
                    byte[] buffer = new byte[16384];
                    int count;
                    while ((count = tar.read(buffer)) != -1) output.write(buffer, 0, count);
                    ntdll = output.toByteArray();
                    break;
                }
            }
        }
        assertNotNull("Bundled Wine ntdll.so was not found", ntdll);
        assertEquals(WineLocaleBinaryPatch.ORIGINAL_SHA256, WineLocaleBinaryPatch.sha256(ntdll));
        assertArrayEquals(new byte[]{0x75, 0x3c},
                Arrays.copyOfRange(ntdll, WineLocaleBinaryPatch.OFFSET, WineLocaleBinaryPatch.OFFSET + 2));
    }
}
