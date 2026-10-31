package com.winlator.alsaserver;

import com.winlator.accessibility.NvdaDiagnosticLog;
import com.winlator.sysvshm.SysVSharedMemory;
import com.winlator.xconnector.ConnectedClient;
import com.winlator.xconnector.RequestHandler;
import com.winlator.xconnector.XConnectorEpoll;
import com.winlator.xconnector.XInputStream;
import com.winlator.xconnector.XOutputStream;
import com.winlator.xconnector.XStreamLock;

import java.io.IOException;
import java.nio.ByteBuffer;

public class ALSARequestHandler implements RequestHandler {
    private int maxSHMemoryId = 0;

    @Override
    public boolean handleRequest(ConnectedClient client) throws IOException {
        ALSAClient alsaClient = (ALSAClient)client.getTag();
        XInputStream inputStream = client.getInputStream();
        XOutputStream outputStream = client.getOutputStream();

        if (inputStream.available() < 5) return false;
        byte requestCode = inputStream.readByte();
        int requestLength = inputStream.readInt();
        if (requestLength < 0 || requestLength > 8 * 1024 * 1024) {
            NvdaDiagnosticLog.record("audio.alsa.request.error",
                    "client="+alsaClient.getDiagnosticId()+"; code="+requestCode+"; length="+requestLength+"; reason=invalid-length");
            throw new IOException("Invalid ALSA request length");
        }

        switch (requestCode) {
            case RequestCodes.CLOSE:
                alsaClient.release();
                break;
            case RequestCodes.START:
                alsaClient.start();
                break;
            case RequestCodes.STOP:
                alsaClient.stop();
                break;
            case RequestCodes.PAUSE:
                alsaClient.pause();
                break;
            case RequestCodes.PREPARE:
                if (inputStream.available() < requestLength) return false;

                int channels = inputStream.readByte() & 0xff;
                int dataTypeIndex = inputStream.readByte() & 0xff;
                int sampleRate = inputStream.readInt();
                int bufferSize = inputStream.readInt();
                if (dataTypeIndex >= ALSAClient.DataType.values().length) {
                    NvdaDiagnosticLog.record("audio.alsa.request.error",
                            "client="+alsaClient.getDiagnosticId()+"; code=prepare; dataType="+dataTypeIndex+"; reason=unsupported-format");
                    throw new IOException("Unsupported ALSA data type");
                }
                alsaClient.setChannels(channels);
                alsaClient.setDataType(ALSAClient.DataType.values()[dataTypeIndex]);
                alsaClient.setSampleRate(sampleRate);
                alsaClient.setBufferSize(bufferSize);
                alsaClient.prepare();

                if (ALSAClient.USE_SHARED_MEMORY) createSharedMemory(alsaClient, outputStream);
                else alsaClient.reportTransport("socket", alsaClient.getBufferSizeInBytes(), true);
                break;
            case RequestCodes.WRITE:
                ByteBuffer sharedBuffer = alsaClient.getSharedBuffer();
                if (sharedBuffer != null) {
                    ByteBuffer aux = alsaClient.getAuxBuffer();
                    if (requestLength > aux.capacity()) {
                        NvdaDiagnosticLog.record("audio.alsa.request.error",
                                "client="+alsaClient.getDiagnosticId()+"; code=write; length="+requestLength
                                        +"; capacity="+aux.capacity()+"; reason=shared-buffer-overflow");
                        throw new IOException("ALSA shared buffer request too large");
                    }
                    copySharedBuffer(alsaClient, requestLength, outputStream);
                    alsaClient.writeDataToTrack(aux);
                    sharedBuffer.putInt(0, alsaClient.pointer());
                }
                else {
                    if (inputStream.available() < requestLength) return false;
                    alsaClient.writeDataToTrack(inputStream.readByteBuffer(requestLength));
                }
                break;
            case RequestCodes.DRAIN:
                alsaClient.drain();
                break;
            case RequestCodes.POINTER:
                try (XStreamLock lock = outputStream.lock()) {
                    outputStream.writeInt(alsaClient.pointer());
                }
                break;
            case RequestCodes.MIN_BUFFER_SIZE:
                byte channelsForMinimum = inputStream.readByte();
                int minimumType = inputStream.readByte() & 0xff;
                int rateForMinimum = inputStream.readInt();
                if (minimumType >= ALSAClient.DataType.values().length) {
                    NvdaDiagnosticLog.record("audio.alsa.request.error",
                            "client="+alsaClient.getDiagnosticId()+"; code=min-buffer; dataType="+minimumType+"; reason=unsupported-format");
                    throw new IOException("Unsupported ALSA minimum-buffer data type");
                }
                ALSAClient.DataType dataType = ALSAClient.DataType.values()[minimumType];
                int minBufferSize = ALSAClient.latencyMillisToBufferSize(alsaClient.options.latencyMillis, channelsForMinimum, dataType, rateForMinimum);

                try (XStreamLock lock = outputStream.lock()) {
                    outputStream.writeInt(minBufferSize);
                }
                break;
            default:
                NvdaDiagnosticLog.record("audio.alsa.request.error",
                        "client="+alsaClient.getDiagnosticId()+"; code="+requestCode+"; length="+requestLength+"; reason=unknown-request");
                break;
        }
        return true;
    }

    private void copySharedBuffer(ALSAClient alsaClient, int requestLength, XOutputStream outputStream) throws IOException {
        ByteBuffer sharedBuffer = alsaClient.getSharedBuffer();
        ByteBuffer auxBuffer = alsaClient.getAuxBuffer();

        auxBuffer.position(0).limit(requestLength);
        sharedBuffer.position(ALSAClient.BUFFER_OFFSET).limit(ALSAClient.BUFFER_OFFSET + requestLength);
        auxBuffer.put(sharedBuffer);

        try (XStreamLock lock = outputStream.lock()) {
            outputStream.writeByte((byte)1);
        }
    }

    private void createSharedMemory(ALSAClient alsaClient, XOutputStream outputStream) throws IOException {
        int shmSize = alsaClient.getBufferSizeInBytes() + ALSAClient.BUFFER_OFFSET;
        int fd = SysVSharedMemory.createMemoryFd("alsa-shm"+(++maxSHMemoryId), shmSize);

        boolean ready = false;
        if (fd >= 0) {
            ByteBuffer buffer = SysVSharedMemory.mapSHMSegment(fd, shmSize, 0, false);
            if (buffer != null) {
                alsaClient.setSharedBuffer(buffer);
                ready = true;
            }
        }
        alsaClient.reportTransport("shared-memory", shmSize, ready);

        try (XStreamLock lock = outputStream.lock()) {
            outputStream.writeByte((byte)0);
            outputStream.setAncillaryFd(fd);
        }
        finally {
            if (fd >= 0) XConnectorEpoll.closeFd(fd);
        }
    }
}
