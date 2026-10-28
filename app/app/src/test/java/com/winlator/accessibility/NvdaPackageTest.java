package com.winlator.accessibility;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import static org.junit.Assert.*;

public class NvdaPackageTest {
    @Rule public TemporaryFolder temporary = new TemporaryFolder();
    private byte[] archive(String name) throws Exception {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        try(ZipOutputStream zip=new ZipOutputStream(bytes)) {
            for(String path:new String[]{name,"documentation/copying.txt"}) {
                zip.putNextEntry(new ZipEntry(path));zip.write("fixture".getBytes(StandardCharsets.UTF_8));zip.closeEntry();
            }
        }
        return bytes.toByteArray();
    }
    private String digest(byte[] bytes) throws Exception {
        StringBuilder out=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))out.append(String.format("%02x",b&255));return out.toString();
    }
    @Test public void installsVerifiedRuntimeAndKeepsUserConfigurationAcrossReuse() throws Exception {
        File base=temporary.newFolder("nvda"), config=new File(base,"config");assertTrue(config.mkdir());
        File settings=new File(config,"nvda.ini");NvdaPackage.write(settings,"user voice settings");
        byte[] bytes=archive("nvda.exe");String hash=digest(bytes);
        File installed=NvdaPackage.install(base,new ByteArrayInputStream(bytes),"2026.3",hash);
        assertTrue(new File(installed,"nvda.exe").isFile());
        assertEquals(hash,NvdaPackage.read(new File(installed,"package.sha256")));
        File reused=NvdaPackage.install(base,new ByteArrayInputStream(bytes),"2026.3",hash);
        assertEquals(installed,reused);assertEquals("user voice settings",NvdaPackage.read(settings));
    }
    @Test public void checksumFailureLeavesNoUsableInstallation() throws Exception {
        File base=temporary.newFolder("bad-checksum");byte[] bytes=archive("nvda.exe");
        try {NvdaPackage.install(base,new ByteArrayInputStream(bytes),"2026.3",new String(new char[64]).replace('\0','0'));fail();}
        catch(IOException expected) { }
        assertEquals(0,base.list().length);
    }
    @Test public void rejectsZipTraversalWithoutWritingOutsideRuntime() throws Exception {
        File base=temporary.newFolder("unsafe");byte[] bytes=archive("../../outside.exe");
        try {NvdaPackage.install(base,new ByteArrayInputStream(bytes),"2026.3",digest(bytes));fail();}
        catch(IOException expected) { }
        assertFalse(new File(base.getParentFile(),"outside.exe").exists());assertEquals(0,base.list().length);
    }
    @Test public void incompleteRuntimeDoesNotReplaceExistingUserConfiguration() throws Exception {
        File base=temporary.newFolder("incomplete"),config=new File(base,"config");assertTrue(config.mkdir());
        File settings=new File(config,"nvda.ini");NvdaPackage.write(settings,"keep");
        byte[] bytes=archive("other.exe");
        try {NvdaPackage.install(base,new ByteArrayInputStream(bytes),"2026.3",digest(bytes));fail();}
        catch(IOException expected) { }
        assertEquals("keep",NvdaPackage.read(settings));assertEquals(1,base.list().length);
    }
}
