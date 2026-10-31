package com.winlator.core;

import android.system.ErrnoException;
import android.system.Os;

import com.winlator.xenvironment.RootFS;

import java.io.File;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * Reversible, hash-pinned locale initialization patch for Winlator's bundled Wine 10.10.
 *
 * Wine's unix_to_win_locale() normally trusts setlocale() unless the result is empty or
 * exactly "C". On Android/Winlator this can leave the Windows locale at en-US even when
 * the container explicitly requests zh_CN.UTF-8. For the opt-in Chinese profile only,
 * this changes one conditional branch so unix_to_win_locale() reads LC_ALL directly.
 *
 * The shared Wine binary is restored when a non-Chinese container starts. Unknown
 * binaries are never modified.
 */
public final class WineLocaleBinaryPatch {
    public static final String ORIGINAL_SHA256 =
            "8e56504a870c8b00ac76df8540c73f26cd33af96ca682600b750721cdde296ca";
    public static final String PATCHED_SHA256 =
            "1d2708d8eaea7c73cde30b3d2b6f3607f64f3fca39c2a62973a7c0406d1dade4";
    public static final int OFFSET = 0x1192a;

    private static final byte[] ORIGINAL_BYTES = new byte[]{0x75, 0x3c};
    private static final byte[] PATCHED_BYTES = new byte[]{(byte)0xeb, 0x00};
    private static final String RELATIVE_PATH = "lib/wine/x86_64-unix/ntdll.so";

    private WineLocaleBinaryPatch() {}

    public static final class Result {
        public final String state;
        public final String sha256;
        public final boolean enabled;

        private Result(String state, String sha256, boolean enabled) {
            this.state = state;
            this.sha256 = sha256 == null ? "" : sha256;
            this.enabled = enabled;
        }

        public String details() {
            return "enabled=" + enabled + "; state=" + state + "; sha256=" + sha256
                    + "; offset=0x" + Integer.toHexString(OFFSET);
        }
    }

    public static Result synchronize(RootFS rootFS, boolean enabled) {
        File wineDir = new File(rootFS.getRootDir(), rootFS.getWinePath());
        File target = new File(wineDir, RELATIVE_PATH);
        byte[] data = FileUtils.read(target);
        if (data == null) return new Result("missing", "", enabled);

        String current = sha256(data);
        if (enabled && PATCHED_SHA256.equals(current))
            return new Result("already-enabled", current, true);
        if (!enabled && ORIGINAL_SHA256.equals(current))
            return new Result("already-original", current, false);

        if (enabled && !ORIGINAL_SHA256.equals(current))
            return new Result("unsupported-binary", current, true);
        if (!enabled && !PATCHED_SHA256.equals(current))
            return new Result("unmanaged-disabled", current, false);

        byte[] from = enabled ? ORIGINAL_BYTES : PATCHED_BYTES;
        byte[] to = enabled ? PATCHED_BYTES : ORIGINAL_BYTES;
        if (!matches(data, OFFSET, from))
            return new Result("unexpected-instructions", current, enabled);

        byte[] changed = data.clone();
        System.arraycopy(to, 0, changed, OFFSET, to.length);
        String expectedHash = enabled ? PATCHED_SHA256 : ORIGINAL_SHA256;
        String changedHash = sha256(changed);
        if (!expectedHash.equals(changedHash))
            return new Result("verification-failed", changedHash, enabled);

        File temporary = new File(target.getParentFile(), target.getName() + ".winlator-locale.tmp");
        if (temporary.exists() && !temporary.delete())
            return new Result("temporary-delete-failed", current, enabled);
        if (!FileUtils.write(temporary, changed))
            return new Result("write-failed", current, enabled);

        FileUtils.chmod(temporary, 0755);
        try {
            Os.rename(temporary.getAbsolutePath(), target.getAbsolutePath());
        }
        catch (ErrnoException error) {
            temporary.delete();
            return new Result("rename-failed-" + error.errno, current, enabled);
        }

        byte[] installed = FileUtils.read(target);
        String installedHash = installed == null ? "" : sha256(installed);
        if (!expectedHash.equals(installedHash))
            return new Result("post-write-verification-failed", installedHash, enabled);

        return new Result(enabled ? "enabled" : "restored", installedHash, enabled);
    }

    static boolean matches(byte[] data, int offset, byte[] expected) {
        if (data == null || expected == null || offset < 0 || offset + expected.length > data.length)
            return false;
        for (int i = 0; i < expected.length; i++) {
            if (data[offset + i] != expected[i]) return false;
        }
        return true;
    }

    static String sha256(byte[] data) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(data);
            StringBuilder result = new StringBuilder(hash.length * 2);
            for (byte value : hash) result.append(String.format(java.util.Locale.ROOT, "%02x", value & 0xff));
            return result.toString();
        }
        catch (NoSuchAlgorithmException error) {
            throw new IllegalStateException(error);
        }
    }
}
