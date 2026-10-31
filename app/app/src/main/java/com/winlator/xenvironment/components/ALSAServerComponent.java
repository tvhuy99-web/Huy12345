package com.winlator.xenvironment.components;

import android.content.Context;
import android.media.AudioManager;

import com.winlator.accessibility.NvdaDiagnosticLog;
import com.winlator.alsaserver.ALSAClient;
import com.winlator.alsaserver.ALSAClientConnectionHandler;
import com.winlator.alsaserver.ALSARequestHandler;
import com.winlator.xconnector.UnixSocketConfig;
import com.winlator.xconnector.XConnectorEpoll;
import com.winlator.xenvironment.EnvironmentComponent;

public class ALSAServerComponent extends EnvironmentComponent {
    private XConnectorEpoll connector;
    private final UnixSocketConfig socketConfig;
    private final ALSAClient.Options options;

    public ALSAServerComponent(UnixSocketConfig socketConfig, ALSAClient.Options options) {
        this.socketConfig = socketConfig;
        this.options = options;
    }

    @Override
    public void start() {
        if (connector != null) return;
        Context context = environment.getContext();
        ALSAClient.assignFramesPerBuffer(context);
        AudioManager manager = (AudioManager)context.getSystemService(Context.AUDIO_SERVICE);
        String nativeRate = manager != null ? manager.getProperty(AudioManager.PROPERTY_OUTPUT_SAMPLE_RATE) : null;
        String nativeFrames = manager != null ? manager.getProperty(AudioManager.PROPERTY_OUTPUT_FRAMES_PER_BUFFER) : null;
        int musicVolume = manager != null ? manager.getStreamVolume(AudioManager.STREAM_MUSIC) : -1;
        int musicMax = manager != null ? manager.getStreamMaxVolume(AudioManager.STREAM_MUSIC) : -1;
        boolean musicMuted = manager != null && manager.isStreamMute(AudioManager.STREAM_MUSIC);
        NvdaDiagnosticLog.record("audio.alsa.server",
                "state=starting; latencyMillis="+options.latencyMillis
                        +"; performanceMode="+options.performanceMode
                        +"; volume="+options.volume
                        +"; sharedMemory="+ALSAClient.USE_SHARED_MEMORY
                        +"; nativeSampleRate="+String.valueOf(nativeRate)
                        +"; nativeFramesPerBuffer="+String.valueOf(nativeFrames)
                        +"; musicVolume="+musicVolume+"/"+musicMax
                        +"; musicMuted="+musicMuted);
        try {
            connector = new XConnectorEpoll(socketConfig, new ALSAClientConnectionHandler(options), new ALSARequestHandler());
            connector.setMultithreadedClients(true);
            connector.start();
            NvdaDiagnosticLog.record("audio.alsa.server", "state=listening");
        }
        catch (RuntimeException error) {
            NvdaDiagnosticLog.error("audio.alsa.server.error", error);
            connector = null;
            throw error;
        }
    }

    @Override
    public void stop() {
        if (connector != null) {
            NvdaDiagnosticLog.record("audio.alsa.server", "state=stopping");
            connector.destroy();
            connector = null;
            NvdaDiagnosticLog.record("audio.alsa.server", "state=stopped");
        }
    }
}
