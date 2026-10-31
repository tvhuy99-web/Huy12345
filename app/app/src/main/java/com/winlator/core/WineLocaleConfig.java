package com.winlator.core;

import com.winlator.accessibility.NvdaDiagnosticLog;
import com.winlator.container.Container;
import com.winlator.xenvironment.RootFS;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.util.Map;

/**
 * Opt-in Wine locale profile for legacy ANSI Windows games.
 *
 * The profile applies before Wine starts. It is deliberately scoped to one
 * container; the Android UI language and other containers are not changed.
 */
public final class WineLocaleConfig {
    public static final String EXTRA_KEY = "wineLocaleProfile";
    public static final String DEFAULT = "";
    public static final String CHINESE_SIMPLIFIED = "zh_CN";

    // Match the compiled glibc directory name in RootFS exactly. The APK 53
    // log proved that setting zh_CN.UTF-8 without compiled locale data falls
    // back to en_US and leaves Wine GetACP() at 1252.
    static final String CHINESE_POSIX_LOCALE = "zh_CN.utf8";
    static final String CHINESE_LOCALE_RELATIVE_PATH = "usr/lib/locale/zh_CN.utf8";

    private static final String FONT_ASSOC_KEY = "System\\ControlSet001\\Control\\FontAssoc\\Associated Charset";
    private static final String FONT_ASSOC_NAME = "ANSI(00)";
    private static final String FONT_ASSOC_MANAGED = "wineLocaleFontAssocManaged";
    private static final String FONT_ASSOC_PREVIOUS = "wineLocaleFontAssocPrevious";
    private static final String MISSING_VALUE = "__winlator_locale_missing__";

    private WineLocaleConfig() {}

    public static boolean isChineseSimplified(String profile) {
        return CHINESE_SIMPLIFIED.equals(profile);
    }

    /**
     * Ensure glibc can actually resolve zh_CN before Wine calls setlocale().
     *
     * RootFS already ships localedef, the zh_CN source and the UTF-8 charmap,
     * but APK 53 did not ship the compiled zh_CN locale directory. Running
     * RootFS' own ARM64 localedef avoids cross-version locale binaries.
     */
    public static boolean ensureCompiledLocale(RootFS rootFS, String profile) {
        if (!isChineseSimplified(profile)) return true;

        File rootDir = rootFS.getRootDir();
        File localeDir = new File(rootDir, CHINESE_LOCALE_RELATIVE_PATH);
        if (isCompiledLocaleReady(localeDir)) {
            NvdaDiagnosticLog.record("wine.locale.compile",
                    "profile=zh_CN; state=ready; source=existing; path="+CHINESE_LOCALE_RELATIVE_PATH);
            return true;
        }

        File localedef = new File(rootDir, "usr/bin/localedef");
        File localeSource = new File(rootDir, "usr/share/i18n/locales/zh_CN");
        File charmap = new File(rootDir, "usr/share/i18n/charmaps/UTF-8.gz");
        File i18nRoot = new File(rootDir, "usr/share/i18n");
        File libDir = new File(rootDir, "usr/lib");
        File gconvDir = new File(libDir, "gconv");
        File localeParent = localeDir.getParentFile();

        if (!localedef.isFile() || !localeSource.isFile() || !charmap.isFile()) {
            NvdaDiagnosticLog.record("wine.locale.compile",
                    "profile=zh_CN; state=missing-input; localedef="+localedef.isFile()+
                    "; source="+localeSource.isFile()+"; charmap="+charmap.isFile());
            return false;
        }

        try {
            FileUtils.delete(localeDir);
            if (localeParent != null) localeParent.mkdirs();

            ProcessBuilder builder = new ProcessBuilder(
                    localedef.getAbsolutePath(),
                    "--no-archive",
                    "-c",
                    "-f", "UTF-8",
                    "-i", "zh_CN",
                    localeDir.getAbsolutePath());
            builder.redirectErrorStream(true);

            Map<String, String> environment = builder.environment();
            environment.put("I18NPATH", i18nRoot.getAbsolutePath());
            environment.put("LOCPATH", localeParent.getAbsolutePath());
            environment.put("LD_LIBRARY_PATH", libDir.getAbsolutePath());
            if (gconvDir.isDirectory()) environment.put("GCONV_PATH", gconvDir.getAbsolutePath());
            environment.put("PATH", new File(rootDir, "usr/bin").getAbsolutePath()+":/system/bin");

            java.lang.Process process = builder.start();
            int outputCharacters = 0;
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    outputCharacters += line.length();
                    // Do not copy localedef paths/messages into the diagnostic log.
                }
            }

            int status = process.waitFor();
            boolean ready = status == 0 && isCompiledLocaleReady(localeDir);
            NvdaDiagnosticLog.record("wine.locale.compile",
                    "profile=zh_CN; state="+(ready ? "generated" : "failed")+
                    "; exit="+status+"; outputCharacters="+outputCharacters+
                    "; ctype="+new File(localeDir, "LC_CTYPE").isFile()+
                    "; collate="+new File(localeDir, "LC_COLLATE").isFile()+
                    "; messages="+new File(localeDir, "LC_MESSAGES/SYS_LC_MESSAGES").isFile());
            if (!ready) FileUtils.delete(localeDir);
            return ready;
        }
        catch (Exception e) {
            FileUtils.delete(localeDir);
            NvdaDiagnosticLog.error("wine.locale.compile.error", e);
            return false;
        }
    }

    static boolean isCompiledLocaleReady(File localeDir) {
        return new File(localeDir, "LC_CTYPE").isFile()
                && new File(localeDir, "LC_COLLATE").isFile()
                && new File(localeDir, "LC_MESSAGES/SYS_LC_MESSAGES").isFile();
    }

    /** Explicit advanced environment overrides take priority. */
    public static void applyEnvironment(EnvVars envVars, String profile, EnvVars userOverrides) {
        if (!isChineseSimplified(profile)) return;
        if (userOverrides == null || !userOverrides.has("LC_ALL"))
            envVars.put("LC_ALL", CHINESE_POSIX_LOCALE);
        if (userOverrides == null || !userOverrides.has("LANG"))
            envVars.put("LANG", CHINESE_POSIX_LOCALE);
        if (userOverrides == null || !userOverrides.has("LANGUAGE"))
            envVars.put("LANGUAGE", "zh_CN:zh");
        if (userOverrides == null || !userOverrides.has("LC_CTYPE"))
            envVars.put("LC_CTYPE", CHINESE_POSIX_LOCALE);
        if (userOverrides == null || !userOverrides.has("LC_MESSAGES"))
            envVars.put("LC_MESSAGES", CHINESE_POSIX_LOCALE);
    }

    /**
     * Align ANSI_CHARSET GDI rendering with Wine's active ANSI code page.
     * Record and restore the original setting instead of permanently changing
     * another program's font configuration.
     *
     * @return true when the container's saved ownership metadata changed.
     */
    public static boolean synchronizeFontAssociation(Container container) {
        boolean enabled = isChineseSimplified(container.getExtra(EXTRA_KEY));
        boolean managed = "t".equals(container.getExtra(FONT_ASSOC_MANAGED));
        if (!enabled && !managed) return false;

        File registry = new File(container.getRootDir(), ".wine/system.reg");
        if (!registry.isFile()) return false;

        try (WineRegistryEditor editor = new WineRegistryEditor(registry)) {
            String current = editor.getStringValue(FONT_ASSOC_KEY, FONT_ASSOC_NAME);
            if (enabled) {
                if (!managed) {
                    container.putExtra(FONT_ASSOC_PREVIOUS, current == null ? MISSING_VALUE : current);
                    container.putExtra(FONT_ASSOC_MANAGED, "t");
                }
                if (!"yes".equalsIgnoreCase(current)) {
                    editor.setStringValue(FONT_ASSOC_KEY, FONT_ASSOC_NAME, "yes");
                }
                return !managed;
            }

            // Only revert if the value still matches the value we installed.
            if ("yes".equalsIgnoreCase(current)) {
                String previous = container.getExtra(FONT_ASSOC_PREVIOUS, MISSING_VALUE);
                if (MISSING_VALUE.equals(previous)) editor.removeValue(FONT_ASSOC_KEY, FONT_ASSOC_NAME);
                else editor.setStringValue(FONT_ASSOC_KEY, FONT_ASSOC_NAME, previous);
            }
            container.putExtra(FONT_ASSOC_MANAGED, null);
            container.putExtra(FONT_ASSOC_PREVIOUS, null);
            return true;
        }
    }
}
