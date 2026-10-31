package com.winlator.core;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.io.File;
import java.nio.file.Files;

/** JVM-level regression coverage for the opt-in Wine locale switch. */
public class WineLocaleConfigTest {
    @Test public void defaultProfileDoesNotOverrideWineLocale() {
        EnvVars environment = new EnvVars();
        environment.put("LC_ALL", "en_US.UTF-8");
        WineLocaleConfig.applyEnvironment(environment, WineLocaleConfig.DEFAULT, null);
        assertEquals("en_US.UTF-8", environment.get("LC_ALL"));
        assertFalse(environment.has("LANG"));
    }

    @Test public void chineseProfileSelectsLocaleBeforeWineStarts() {
        EnvVars environment = new EnvVars();
        environment.put("LC_ALL", "en_US.UTF-8");
        WineLocaleConfig.applyEnvironment(environment, WineLocaleConfig.CHINESE_SIMPLIFIED, new EnvVars());
        assertEquals("zh_CN.utf8", environment.get("LC_ALL"));
        assertEquals("zh_CN.utf8", environment.get("LANG"));
        assertEquals("zh_CN:zh", environment.get("LANGUAGE"));
        assertEquals("zh_CN.utf8", environment.get("LC_CTYPE"));
        assertEquals("zh_CN.utf8", environment.get("LC_MESSAGES"));
    }

    @Test public void containerOverridesAreNotLost() {
        EnvVars overrides = new EnvVars();
        overrides.put("LC_ALL", "ja_JP.UTF-8");
        EnvVars environment = new EnvVars();
        environment.putAll(overrides);
        WineLocaleConfig.applyEnvironment(environment, WineLocaleConfig.CHINESE_SIMPLIFIED, overrides);
        assertEquals("ja_JP.UTF-8", environment.get("LC_ALL"));
        assertEquals("zh_CN.utf8", environment.get("LANG"));
    }

    @Test public void explicitLanguageOverrideIsPreserved() {
        EnvVars overrides = new EnvVars();
        overrides.put("LANG", "ko_KR.UTF-8");
        EnvVars environment = new EnvVars();
        environment.putAll(overrides);
        WineLocaleConfig.applyEnvironment(environment, WineLocaleConfig.CHINESE_SIMPLIFIED, overrides);
        assertEquals("zh_CN.utf8", environment.get("LC_ALL"));
        assertEquals("ko_KR.UTF-8", environment.get("LANG"));
        assertEquals("zh_CN:zh", environment.get("LANGUAGE"));
        assertTrue(environment.has("LC_ALL"));
    }

    @Test public void compiledLocaleReadinessRequiresCoreGlibcFiles() throws Exception {
        File root = Files.createTempDirectory("wine-locale-test").toFile();
        File messages = new File(root, "LC_MESSAGES");
        messages.mkdirs();
        assertFalse(WineLocaleConfig.isCompiledLocaleReady(root));

        new File(root, "LC_CTYPE").createNewFile();
        new File(root, "LC_COLLATE").createNewFile();
        new File(messages, "SYS_LC_MESSAGES").createNewFile();
        assertTrue(WineLocaleConfig.isCompiledLocaleReady(root));

        FileUtils.delete(root);
    }
}
