package com.winlator.accessibility;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.DigestInputStream;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** Installs only the bundled runtime; the user's NVDA configuration lives separately. */
public final class NvdaPackage {
    public static final long MAX_BYTES = 700L * 1024 * 1024;
    private NvdaPackage() {}

    public static File install(File base, InputStream archive, String version, String sha256) throws Exception {
        if (!version.matches("[0-9.]+") || !sha256.matches("[0-9a-f]{64}")) throw new IOException("Invalid package metadata");
        File target = new File(base, "runtime-" + version + "-" + sha256.substring(0, 12));
        File marker = new File(target, "package.sha256");
        if (marker.isFile() && new File(target,"nvda.exe").isFile() && sha256.equals(read(marker))) {
            archive.close(); return target;
        }
        if (!base.isDirectory() && !base.mkdirs()) throw new IOException("Cannot create NVDA folder");
        File stage = new File(base, ".install-" + UUID.randomUUID());
        if (!stage.mkdir()) throw new IOException("Cannot create installation folder");
        try {
            MessageDigest hash = MessageDigest.getInstance("SHA-256");
            try (DigestInputStream digest = new DigestInputStream(archive, hash);
                 ZipInputStream zip = new ZipInputStream(digest)) {
                extract(zip, stage);
                // Drain the central directory too; the digest covers the whole asset.
                byte[] buffer = new byte[32768]; while (digest.read(buffer) != -1) { }
            }
            if (!sha256.equals(hex(hash.digest()))) throw new IOException("NVDA package checksum mismatch");
            if (!new File(stage,"nvda.exe").isFile() || !new File(stage,"documentation/copying.txt").isFile())
                throw new IOException("Incomplete NVDA package");
            write(new File(stage,"package.sha256"),sha256);
            // A damaged runtime is disposable; no user configuration is stored here.
            if (target.exists()) delete(target);
            if (!stage.renameTo(target)) throw new IOException("Cannot finish NVDA installation");
            return target;
        } finally { if (stage.exists()) delete(stage); }
    }
    static void extract(ZipInputStream zip, File destination) throws IOException {
        String prefix = destination.getCanonicalPath() + File.separator;
        long total = 0; int entries = 0; ZipEntry entry;
        byte[] buffer = new byte[32768];
        while ((entry = zip.getNextEntry()) != null) {
            if (++entries > 5000 || entry.getName().indexOf('\\') >= 0 || entry.getName().startsWith("/"))
                throw new IOException("Invalid NVDA archive entry");
            File file = new File(destination,entry.getName());
            if (!file.getCanonicalPath().startsWith(prefix)) throw new IOException("Unsafe archive path");
            if (entry.isDirectory()) {
                if (!file.isDirectory() && !file.mkdirs()) throw new IOException("Cannot create runtime folder");
            } else {
                File parent = file.getParentFile();
                if (!parent.isDirectory() && !parent.mkdirs()) throw new IOException("Cannot create runtime folder");
                try (OutputStream output = new FileOutputStream(file)) {
                    int n;
                    while ((n = zip.read(buffer)) != -1) {
                        if (Thread.currentThread().isInterrupted()) throw new InterruptedIOException("NVDA installation cancelled");
                        total += n; if (total > MAX_BYTES) throw new IOException("NVDA archive exceeds limit");
                        output.write(buffer,0,n);
                    }
                }
            }
            zip.closeEntry();
        }
    }
    public static String read(File file) throws IOException {
        if (file.length() > 16384) throw new IOException("State file exceeds limit");
        try (InputStream in = new FileInputStream(file); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[2048]; int n;
            while ((n = in.read(buffer)) != -1) {
                if (out.size() + n > 16384) throw new IOException("State file exceeds limit");
                out.write(buffer,0,n);
            }
            return out.toString("UTF-8");
        }
    }
    static void write(File file, String text) throws IOException {
        try (OutputStream out = new FileOutputStream(file)) { out.write(text.getBytes(StandardCharsets.UTF_8)); }
    }
    private static String hex(byte[] bytes) {
        StringBuilder out = new StringBuilder();
        for (byte b:bytes) out.append(String.format(java.util.Locale.ROOT,"%02x",b & 255));
        return out.toString();
    }
    private static void delete(File file) throws IOException {
        // Never follow links in a Wine directory during cleanup.
        if (java.nio.file.Files.isSymbolicLink(file.toPath())) {
            if (!file.delete()) throw new IOException("Cannot remove link"); return;
        }
        File[] children = file.listFiles();
        if (children != null) for (File child:children) delete(child);
        if (!file.delete()) throw new IOException("Cannot remove incomplete runtime");
    }
}
