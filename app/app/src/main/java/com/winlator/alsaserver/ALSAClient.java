package com.winlator.alsaserver;

import android.content.Context;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;

import com.winlator.accessibility.NvdaDiagnosticLog;
import com.winlator.contentdialog.AudioDriverConfigDialog;
import com.winlator.core.KeyValueSet;
import com.winlator.math.Mathf;
import com.winlator.sysvshm.SysVSharedMemory;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.concurrent.atomic.AtomicInteger;

public class ALSAClient {
    public static final boolean USE_SHARED_MEMORY = false;
    public static final byte BUFFER_OFFSET = 4;
    private static final AtomicInteger NEXT_DIAGNOSTIC_ID = new AtomicInteger();

    public enum DataType {
        U8(1), S16LE(2), S16BE(2), FLOATLE(4), FLOATBE(4);
        public final byte byteCount;

        DataType(int byteCount) {
            this.byteCount = (byte)byteCount;
        }
    }

    private final int diagnosticId = NEXT_DIAGNOSTIC_ID.incrementAndGet();
    private DataType dataType = DataType.U8;
    private AudioTrack audioTrack = null;
    private byte channels = 2;
    private int sampleRate = 0;
    private int position;
    private int bufferSize;
    private byte frameBytes;
    private short previousUnderrunCount = 0;
    private int bufferCapacity;
    private ByteBuffer sharedBuffer;
    private ByteBuffer auxBuffer;
    protected final Options options;
    private static short framesPerBuffer = 256;

    private boolean prepared;
    private long writeCalls;
    private long requestedBytes;
    private long writtenBytes;
    private long sampledBytes;
    private long nonZeroSampleBytes;
    private int writeFailures;
    private long lastWriteLogMs;

    public static class Options {
        public short latencyMillis = AudioDriverConfigDialog.DEFAULT_LATENCY_MILLIS;
        public byte performanceMode = AudioTrack.PERFORMANCE_MODE_LOW_LATENCY;
        public float volume = AudioDriverConfigDialog.DEFAULT_VOLUME;

        public static Options fromKeyValueSet(KeyValueSet config) {
            if (config == null || config.isEmpty()) return new Options();
            Options options = new Options();
            switch (config.get("performanceMode")) {
                case "0" :
                    options.performanceMode = AudioTrack.PERFORMANCE_MODE_NONE;
                    break;
                case "1" :
                    options.performanceMode = AudioTrack.PERFORMANCE_MODE_LOW_LATENCY;
                    break;
                case "2" :
                    options.performanceMode = AudioTrack.PERFORMANCE_MODE_POWER_SAVING;
                    break;
            }

            options.volume = config.getFloat("volume", AudioDriverConfigDialog.DEFAULT_VOLUME);
            options.latencyMillis = (short)config.getInt("latencyMillis", AudioDriverConfigDialog.DEFAULT_LATENCY_MILLIS);
            return options;
        }
    }

    public ALSAClient(Options options) {
        this.options = options;
    }

    public int getDiagnosticId() {
        return diagnosticId;
    }

    public void release() {
        if (prepared || writeCalls > 0) logSummary("release");

        if (sharedBuffer != null) {
            SysVSharedMemory.unmapSHMSegment(sharedBuffer, sharedBuffer.capacity());
            sharedBuffer = null;
        }

        if (audioTrack != null) {
            try {
                audioTrack.pause();
                audioTrack.flush();
            }
            catch (RuntimeException error) {
                NvdaDiagnosticLog.error("audio.alsa.release.error", error);
            }
            audioTrack.release();
            audioTrack = null;
        }
        prepared = false;
    }

    public static int getPCMEncoding(DataType dataType) {
        switch (dataType) {
            case U8:
                return AudioFormat.ENCODING_PCM_8BIT;
            case S16LE:
            case S16BE:
                return AudioFormat.ENCODING_PCM_16BIT;
            case FLOATLE:
            case FLOATBE:
                return AudioFormat.ENCODING_PCM_FLOAT;
            default:
                return AudioFormat.ENCODING_DEFAULT;
        }
    }

    public static int getChannelConfig(int channels) {
        return channels <= 1 ? AudioFormat.CHANNEL_OUT_MONO : AudioFormat.CHANNEL_OUT_STEREO;
    }

    public void prepare() {
        release();
        position = 0;
        previousUnderrunCount = 0;
        frameBytes = (byte)(channels * dataType.byteCount);
        writeCalls = requestedBytes = writtenBytes = sampledBytes = nonZeroSampleBytes = 0;
        writeFailures = 0;
        lastWriteLogMs = 0;
        prepared = true;

        if (!isValidBufferSize()) {
            NvdaDiagnosticLog.record("audio.alsa.prepare",
                    "client="+diagnosticId+"; state=invalid-buffer; channels="+channels
                            +"; format="+dataType+"; sampleRate="+sampleRate+"; bufferFrames="+bufferSize
                            +"; frameBytes="+frameBytes);
            return;
        }

        AudioFormat format = new AudioFormat.Builder()
            .setEncoding(getPCMEncoding(dataType))
            .setSampleRate(sampleRate)
            .setChannelMask(getChannelConfig(channels))
            .build();

        try {
            audioTrack = new AudioTrack.Builder()
                .setPerformanceMode(options.performanceMode)
                .setAudioFormat(format)
                .setBufferSizeInBytes(getBufferSizeInBytes())
                .build();

            bufferCapacity = audioTrack.getBufferCapacityInFrames();
            if (options.volume != 1.0f) audioTrack.setVolume(options.volume);
            audioTrack.play();
            NvdaDiagnosticLog.record("audio.alsa.prepare",
                    "client="+diagnosticId+"; state=ready; channels="+channels
                            +"; format="+dataType+"; sampleRate="+sampleRate+"; frameBytes="+frameBytes
                            +"; bufferFrames="+bufferSize+"; bufferBytes="+getBufferSizeInBytes()
                            +"; capacityFrames="+bufferCapacity+"; activeBufferFrames="+audioTrack.getBufferSizeInFrames()
                            +"; trackState="+audioTrack.getState()+"; playState="+audioTrack.getPlayState()
                            +"; sessionId="+audioTrack.getAudioSessionId()+"; performanceMode="+audioTrack.getPerformanceMode()
                            +"; volume="+options.volume);
        }
        catch (RuntimeException error) {
            NvdaDiagnosticLog.error("audio.alsa.prepare.error", error);
            throw error;
        }
    }

    public void start() {
        if (audioTrack != null && audioTrack.getPlayState() != AudioTrack.PLAYSTATE_PLAYING) {
            try {
                audioTrack.play();
                logControl("start");
            }
            catch (RuntimeException error) {
                NvdaDiagnosticLog.error("audio.alsa.start.error", error);
                throw error;
            }
        }
        else logControl("start-noop");
    }

    public void stop() {
        if (audioTrack != null) {
            try {
                audioTrack.stop();
                audioTrack.flush();
                logControl("stop");
            }
            catch (RuntimeException error) {
                NvdaDiagnosticLog.error("audio.alsa.stop.error", error);
                throw error;
            }
        }
        else logControl("stop-no-track");
    }

    public void pause() {
        if (audioTrack != null) {
            try {
                audioTrack.pause();
                logControl("pause");
            }
            catch (RuntimeException error) {
                NvdaDiagnosticLog.error("audio.alsa.pause.error", error);
                throw error;
            }
        }
        else logControl("pause-no-track");
    }

    public void drain() {
        if (audioTrack != null) {
            try {
                audioTrack.flush();
                logControl("drain");
            }
            catch (RuntimeException error) {
                NvdaDiagnosticLog.error("audio.alsa.drain.error", error);
                throw error;
            }
        }
        else logControl("drain-no-track");
    }

    public void writeDataToTrack(ByteBuffer data) {
        if (dataType == DataType.S16LE || dataType == DataType.FLOATLE) {
            data.order(ByteOrder.LITTLE_ENDIAN);
        }
        else if (dataType == DataType.S16BE || dataType == DataType.FLOATBE) {
            data.order(ByteOrder.BIG_ENDIAN);
        }

        data.position(0);
        int requested = data.remaining();
        int sampled = requested;
        int nonZero = 0;
        ByteBuffer probe = data.duplicate();
        for (int i = 0; i < sampled; i++) if (probe.get(i) != 0) nonZero++;
        writeCalls++;
        requestedBytes += requested;
        sampledBytes += sampled;
        nonZeroSampleBytes += nonZero;

        if (audioTrack == null) {
            writeFailures++;
            logWrite("no-track", requested, 0, nonZero, true);
            data.rewind();
            return;
        }

        int before = data.position();
        boolean failed = false;
        do {
            try {
                int bytesWritten = audioTrack.write(data, data.remaining(), AudioTrack.WRITE_BLOCKING);
                if (bytesWritten < 0) {
                    writeFailures++;
                    failed = true;
                    logWrite("write-error-"+bytesWritten, requested, data.position()-before, nonZero, true);
                    break;
                }
                if (bytesWritten == 0 && data.remaining() > 0) {
                    writeFailures++;
                    failed = true;
                    logWrite("zero-write", requested, data.position()-before, nonZero, true);
                    break;
                }
                increaseBufferSizeIfUnderrunOccurs();
            }
            catch (Exception error) {
                writeFailures++;
                failed = true;
                NvdaDiagnosticLog.error("audio.alsa.write.error", error);
                break;
            }
        }
        while (data.position() != data.limit());

        int wrote = data.position()-before;
        writtenBytes += wrote;
        position += data.position();
        if (!failed) logWrite("ok", requested, wrote, nonZero, writeCalls == 1);
        data.rewind();
    }

    private void logControl(String action) {
        NvdaDiagnosticLog.record("audio.alsa.control",
                "client="+diagnosticId+"; action="+action+"; playState="+(audioTrack != null ? audioTrack.getPlayState() : -1)
                        +"; trackState="+(audioTrack != null ? audioTrack.getState() : -1)
                        +"; writes="+writeCalls+"; writtenBytes="+writtenBytes);
    }

    private void logWrite(String state, int requested, int wrote, int nonZero, boolean force) {
        long now = android.os.SystemClock.elapsedRealtime();
        if (!force && now-lastWriteLogMs < 2000) return;
        lastWriteLogMs = now;
        NvdaDiagnosticLog.record("audio.alsa.write",
                "client="+diagnosticId+"; state="+state+"; call="+writeCalls
                        +"; requested="+requested+"; wrote="+wrote+"; nonZeroSampleBytes="+nonZero
                        +"; totalRequested="+requestedBytes+"; totalWritten="+writtenBytes
                        +"; sampledBytes="+sampledBytes+"; totalNonZeroSampleBytes="+nonZeroSampleBytes
                        +"; failures="+writeFailures+"; playState="+(audioTrack != null ? audioTrack.getPlayState() : -1)
                        +"; trackState="+(audioTrack != null ? audioTrack.getState() : -1)
                        +"; underruns="+(audioTrack != null ? audioTrack.getUnderrunCount() : -1)
                        +"; bufferFrames="+bufferSize+"; capacityFrames="+bufferCapacity);
    }

    private void logSummary(String reason) {
        NvdaDiagnosticLog.record("audio.alsa.summary",
                "client="+diagnosticId+"; reason="+reason+"; prepared="+prepared
                        +"; channels="+channels+"; format="+dataType+"; sampleRate="+sampleRate
                        +"; writes="+writeCalls+"; requestedBytes="+requestedBytes+"; writtenBytes="+writtenBytes
                        +"; sampledBytes="+sampledBytes+"; nonZeroSampleBytes="+nonZeroSampleBytes
                        +"; failures="+writeFailures+"; positionFrames="+(frameBytes > 0 ? position/frameBytes : 0)
                        +"; underruns="+(audioTrack != null ? audioTrack.getUnderrunCount() : -1));
    }

    private void increaseBufferSizeIfUnderrunOccurs() {
        int underrunCount = audioTrack.getUnderrunCount();
        if (underrunCount > previousUnderrunCount && bufferSize < bufferCapacity) {
            int before = bufferSize;
            previousUnderrunCount = (short)underrunCount;
            bufferSize += framesPerBuffer;
            int result = audioTrack.setBufferSizeInFrames(bufferSize);
            NvdaDiagnosticLog.record("audio.alsa.underrun",
                    "client="+diagnosticId+"; count="+underrunCount+"; oldBufferFrames="+before
                            +"; requestedBufferFrames="+bufferSize+"; appliedBufferFrames="+result);
        }
    }

    public int pointer() {
        return audioTrack != null ? position / frameBytes : 0;
    }

    public void setDataType(DataType dataType) {
        this.dataType = dataType;
    }

    public void setChannels(int channels) {
        this.channels = (byte)channels;
    }

    public void setSampleRate(int sampleRate) {
        this.sampleRate = sampleRate;
    }

    public void setBufferSize(int bufferSize) {
        this.bufferSize = bufferSize;
    }

    public ByteBuffer getSharedBuffer() {
        return sharedBuffer;
    }

    public void setSharedBuffer(ByteBuffer sharedBuffer) {
        if (sharedBuffer != null) {
            auxBuffer = ByteBuffer.allocateDirect(getBufferSizeInBytes()).order(ByteOrder.LITTLE_ENDIAN);
            this.sharedBuffer = sharedBuffer.order(ByteOrder.LITTLE_ENDIAN);
        }
        else {
            auxBuffer = null;
            this.sharedBuffer = null;
        }
    }

    public ByteBuffer getAuxBuffer() {
        return auxBuffer;
    }

    public void reportTransport(String transport, int bytes, boolean ready) {
        NvdaDiagnosticLog.record("audio.alsa.transport",
                "client="+diagnosticId+"; transport="+transport+"; bytes="+bytes+"; ready="+ready);
    }

    public DataType getDataType() {
        return dataType;
    }

    public byte getChannels() {
        return channels;
    }

    public int getSampleRate() {
        return sampleRate;
    }

    public int getBufferSize() {
        return bufferSize;
    }

    public int getBufferSizeInBytes() {
        return bufferSize * frameBytes;
    }

    public static int bufferSizeToLatencyMillis(int bufferSizeInBytes, int channels, DataType dataType, int sampleRate) {
        byte frameBytes = (byte)(channels * dataType.byteCount);
        float bufferSize = (float)bufferSizeInBytes / frameBytes;
        return (int)((bufferSize / sampleRate) * 1000);
    }

    public static int latencyMillisToBufferSize(int latencyMillis, int channels, DataType dataType, int sampleRate) {
        byte frameBytes = (byte)(channels * dataType.byteCount);
        int bufferSize = (int)Mathf.roundTo((latencyMillis * sampleRate) / 1000.0f, framesPerBuffer, false);
        return bufferSize * frameBytes;
    }

    private boolean isValidBufferSize() {
        return ((bufferSize % frameBytes) == 0) && bufferSize > 0;
    }

    public static void assignFramesPerBuffer(Context context) {
        try {
            AudioManager am = (AudioManager)context.getSystemService(Context.AUDIO_SERVICE);
            String framesPerBufferStr = am.getProperty(AudioManager.PROPERTY_OUTPUT_FRAMES_PER_BUFFER);
            framesPerBuffer = Short.parseShort(framesPerBufferStr);
            if (framesPerBuffer == 0) framesPerBuffer = 256;
        }
        catch (Exception e) {
            framesPerBuffer = 256;
        }
    }
}
