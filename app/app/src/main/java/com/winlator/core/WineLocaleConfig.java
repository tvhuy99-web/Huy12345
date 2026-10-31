package com.winlator.core;

import com.winlator.container.Container;

import java.io.File;

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

    private static final String CHINESE_POSIX_LOCALE = "zh_CN.UTF-8";
    private static final String FONT_ASSOC_KEY = "System\\CurrentControlSet\\Control\\FontAssoc\\Associated Charset";
    private static final String FONT_ASSOC_NAME = "ANSI(00)";
    private static final String FONT_ASSOC_MANAGED = "wineLocaleFontAssocManaged";
    private static final String FONT_ASSOC_PREVIOUS = "wineLocaleFontAssocPrevious";
    private static final String MISSING_VALUE = "__winlator_locale_missing__";

    private WineLocaleConfig() {}

    public static boolean isChineseSimplified(String profile) {
        return CHINESE_SIMPLIFIED.equals(profile);
    }

    /** Explicit advanced environment overrides take priority. */
    public static void applyEnvironment(EnvVars envVars, String profile, EnvVars userOverrides) {
        if (!isChineseSimplified(profile)) return;
        if (userOverrides == null || !userOverrides.has("LC_ALL"))
            envVars.put("LC_ALL", CHINESE_POSIX_LOCALE);
        if (userOverrides == null || !userOverrides.has("LANG"))
            envVars.put("LANG", CHINESE_POSIX_LOCALE);
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
