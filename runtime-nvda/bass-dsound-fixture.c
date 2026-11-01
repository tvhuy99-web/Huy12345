/* SPDX-License-Identifier: MIT. CI-only fake BASS -> DirectSound route. */
#include <windows.h>
#include <mmsystem.h>
#include <stdint.h>
#include <string.h>

typedef struct {
    DWORD dwSize,dwFlags,dwBufferBytes,dwReserved;
    LPWAVEFORMATEX lpwfxFormat;
    GUID guid3DAlgorithm;
} DSBUFFERDESC_MIN;

#ifdef BUILD_DSOUND
typedef struct { void **lpVtbl; } FakeObject;
static uint8_t sampleBuffer[64];
static void *bufferVtbl[21];
static void *dsVtbl[12];
static FakeObject bufferObject={bufferVtbl};
static FakeObject dsObject={dsVtbl};

static HRESULT WINAPI fakeCreateSoundBuffer(void *self,const DSBUFFERDESC_MIN *desc,void **out,void *outer){
    (void)self;(void)desc;(void)outer;
    if(!out)return E_POINTER;
    *out=&bufferObject;
    return S_OK;
}
static HRESULT WINAPI fakeLock(void *self,DWORD offset,DWORD bytes,void **p1,DWORD *b1,void **p2,DWORD *b2,DWORD flags){
    (void)self;(void)offset;(void)flags;
    if(!p1||!b1)return E_POINTER;
    DWORD n=bytes&&bytes<sizeof(sampleBuffer)?bytes:(DWORD)sizeof(sampleBuffer);
    *p1=sampleBuffer;*b1=n;if(p2)*p2=NULL;if(b2)*b2=0;return S_OK;
}
static HRESULT WINAPI fakeUnlock(void *self,void *p1,DWORD b1,void *p2,DWORD b2){
    (void)self;(void)p1;(void)b1;(void)p2;(void)b2;return S_OK;
}
static HRESULT WINAPI fakePlay(void *self,DWORD a,DWORD b,DWORD c){
    (void)self;(void)a;(void)b;(void)c;return S_OK;
}
static void initVtables(void){
    dsVtbl[3]=(void*)(uintptr_t)fakeCreateSoundBuffer;
    bufferVtbl[11]=(void*)(uintptr_t)fakeLock;
    bufferVtbl[12]=(void*)(uintptr_t)fakePlay;
    bufferVtbl[19]=(void*)(uintptr_t)fakeUnlock;
}
HRESULT WINAPI fixtureDirectSoundCreate8(const GUID *guid,void **out,void *outer){
    (void)guid;(void)outer;initVtables();
    if(!out)return E_POINTER;
    *out=&dsObject;
    return S_OK;
}
HRESULT WINAPI fixtureDirectSoundCreate(const GUID *guid,void **out,void *outer){
    return fixtureDirectSoundCreate8(guid,out,outer);
}
#elif defined(BUILD_BASS)
typedef HRESULT (WINAPI *DirectSoundCreate8Fn)(const GUID*,void**,void*);
typedef HRESULT (WINAPI *CreateBufferFn)(void*,const DSBUFFERDESC_MIN*,void**,void*);
typedef HRESULT (WINAPI *LockFn)(void*,DWORD,DWORD,void**,DWORD*,void**,DWORD*,DWORD);
typedef HRESULT (WINAPI *UnlockFn)(void*,void*,DWORD,void*,DWORD);
typedef HRESULT (WINAPI *PlayFn)(void*,DWORD,DWORD,DWORD);
typedef FARPROC (WINAPI *FixtureGetProcAddressFn)(HMODULE,LPCSTR);
typedef HMODULE (WINAPI *FixtureLoadLibraryAFn)(LPCSTR);
static FixtureGetProcAddressFn cachedGetProcAddress;
static FixtureLoadLibraryAFn cachedLoadLibraryA;
static DWORD fixtureInitFlags;
typedef void (CALLBACK *FixtureDspProc)(DWORD,DWORD,void*,DWORD,void*);
static FixtureDspProc fixtureDsp;
static void *fixtureDspUser;
static DWORD fixtureDspHandle=0x1234u;
static DWORD fixtureStreamHandle=0x2345u;

BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID reserved){
    (void)instance;(void)reserved;
    if(reason==DLL_PROCESS_ATTACH){
        HMODULE kernel32=GetModuleHandleA("kernel32.dll");
        if(kernel32){
            cachedGetProcAddress=(FixtureGetProcAddressFn)(uintptr_t)GetProcAddress(kernel32,"GetProcAddress");
            cachedLoadLibraryA=(FixtureLoadLibraryAFn)(uintptr_t)GetProcAddress(kernel32,"LoadLibraryA");
        }
    }
    return TRUE;
}

BOOL WINAPI fixtureBassInit(int device,DWORD freq,DWORD flags,HWND window,const void *guid){
    (void)device;(void)freq;(void)window;(void)guid;
    fixtureInitFlags=flags;
    return (flags&0x40000u)!=0;
}
BOOL WINAPI fixtureBassGetInfo(void *buffer){
    if(!buffer)return FALSE;
    DWORD *words=(DWORD*)buffer;
    for(unsigned i=0;i<14;i++)words[i]=0;
    words[9]=8;
    words[11]=fixtureInitFlags;
    words[13]=44100;
    return TRUE;
}

DWORD WINAPI fixtureBassStreamCreateFile(BOOL memory,const void *file,uint64_t offset,uint64_t length,DWORD flags){
    (void)memory;(void)file;(void)offset;(void)length;(void)flags;
    return fixtureStreamHandle;
}
BOOL WINAPI fixtureBassStreamFree(DWORD handle){
    if(handle!=fixtureStreamHandle)return FALSE;
    fixtureDsp=NULL;fixtureDspUser=NULL;return TRUE;
}
BOOL WINAPI fixtureBassChannelGetInfo(DWORD handle,void *buffer){
    if(handle!=fixtureStreamHandle || !buffer)return FALSE;
    DWORD *words=(DWORD*)buffer;
    for(unsigned i=0;i<7;i++)words[i]=0;
    words[0]=44100;words[1]=2;words[2]=0;
    return TRUE;
}
DWORD WINAPI fixtureBassChannelSetDSP(DWORD handle,FixtureDspProc proc,void *user,int priority){
    (void)priority;
    if(handle!=fixtureStreamHandle || !proc)return 0;
    fixtureDsp=proc;fixtureDspUser=user;return fixtureDspHandle;
}
BOOL WINAPI fixtureBassChannelRemoveDSP(DWORD handle,DWORD dsp){
    if(handle!=fixtureStreamHandle || dsp!=fixtureDspHandle)return FALSE;
    fixtureDsp=NULL;fixtureDspUser=NULL;return TRUE;
}
BOOL WINAPI fixtureBassChannelPlay(DWORD handle,BOOL restart){
    (void)restart;
    if(handle!=fixtureStreamHandle)return FALSE;
    if(fixtureDsp){
        int16_t pcm[32];
        for(unsigned i=0;i<32;i++)pcm[i]=(int16_t)(300+i*17);
        fixtureDsp(fixtureDspHandle,handle,pcm,(DWORD)sizeof(pcm),fixtureDspUser);
    }
    return TRUE;
}

int __cdecl fixtureBassTest(void){
    if(!(fixtureInitFlags&0x40000u))return 8;
    if(!cachedLoadLibraryA || !cachedGetProcAddress)return 9;
    HMODULE ds=cachedLoadLibraryA("dsound.dll");if(!ds)return 10;
    DirectSoundCreate8Fn create=(DirectSoundCreate8Fn)(uintptr_t)cachedGetProcAddress(ds,"DirectSoundCreate8");
    if(!create)return 11;
    void *direct=NULL;if(FAILED(create(NULL,&direct,NULL))||!direct)return 12;
    void **dv=*(void***)direct;CreateBufferFn createBuffer=(CreateBufferFn)(uintptr_t)dv[3];
    WAVEFORMATEX wave={0};wave.wFormatTag=3;wave.nChannels=2;wave.nSamplesPerSec=44100;
    wave.wBitsPerSample=32;wave.nBlockAlign=8;wave.nAvgBytesPerSec=352800;
    DSBUFFERDESC_MIN desc={0};desc.dwSize=sizeof(desc);desc.dwBufferBytes=64;desc.lpwfxFormat=&wave;
    void *buffer=NULL;if(FAILED(createBuffer(direct,&desc,&buffer,NULL))||!buffer)return 13;
    void **bv=*(void***)buffer;LockFn lock=(LockFn)(uintptr_t)bv[11];
    UnlockFn unlock=(UnlockFn)(uintptr_t)bv[19];PlayFn play=(PlayFn)(uintptr_t)bv[12];
    void *p1=NULL,*p2=NULL;DWORD b1=0,b2=0;
    if(FAILED(lock(buffer,0,64,&p1,&b1,&p2,&b2,0)))return 14;
    for(DWORD i=0;i<b1;i++)((uint8_t*)p1)[i]=(uint8_t)(i+1);
    if(p2)for(DWORD i=0;i<b2;i++)((uint8_t*)p2)[i]=(uint8_t)(i+3);
    if(FAILED(unlock(buffer,p1,b1,p2,b2)))return 15;
    if(FAILED(play(buffer,0,0,1)))return 16;
    return 77;
}
#else
#error Select BUILD_DSOUND or BUILD_BASS
#endif
