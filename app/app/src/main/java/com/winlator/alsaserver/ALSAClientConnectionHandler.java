package com.winlator.alsaserver;

import com.winlator.accessibility.NvdaDiagnosticLog;
import com.winlator.xconnector.ConnectedClient;
import com.winlator.xconnector.ConnectionHandler;

public class ALSAClientConnectionHandler implements ConnectionHandler {
    private final ALSAClient.Options options;

    public ALSAClientConnectionHandler(ALSAClient.Options options) {
        this.options = options;
    }

    @Override
    public void handleNewConnection(ConnectedClient client) {
        ALSAClient alsa = new ALSAClient(options);
        client.setTag(alsa);
        NvdaDiagnosticLog.record("audio.alsa.connection", "state=opened; client="+alsa.getDiagnosticId());
    }

    @Override
    public void handleConnectionShutdown(ConnectedClient client) {
        if (client.getTag() != null) {
            ALSAClient alsa = (ALSAClient)client.getTag();
            NvdaDiagnosticLog.record("audio.alsa.connection", "state=closing; client="+alsa.getDiagnosticId());
            alsa.release();
            NvdaDiagnosticLog.record("audio.alsa.connection", "state=closed; client="+alsa.getDiagnosticId());
        }
    }
}
