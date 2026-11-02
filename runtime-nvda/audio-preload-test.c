/* SPDX-License-Identifier: MIT. CI only: verify the PID-scoped probe catches early static and dynamic audio routes. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <mmsystem.h>
#include <stdio.h>
#include <stdint.h>

int main(void){
    (void)GetForegroundWindow();
    printf("%lu\n",(unsigned long)GetCurrentProcessId());
    fflush(stdout);
    Sleep(1200);
    char pcm[16]={0,1,0,2,0,3,0,4,0,5,0,6,0,7,0,8};
    WAVEHDR header={0};
    header.lpData=pcm;
    header.dwBufferLength=sizeof(pcm);
    waveOutWrite((HWAVEOUT)(ULONG_PTR)1,&header,sizeof(header));
    HMODULE bass=LoadLibraryA("bass.dll");
    if(!bass)return 20;
    typedef BOOL (WINAPI *BassInitFn)(int,DWORD,DWORD,HWND,const void*);
    typedef DWORD (WINAPI *BassStreamCreateFileFn)(BOOL,const void*,uint64_t,uint64_t,DWORD);
    typedef BOOL (WINAPI *BassChannelPlayFn)(DWORD,BOOL);
    typedef BOOL (WINAPI *BassStreamFreeFn)(DWORD);
    typedef int (__cdecl *BassTestFn)(void);
    typedef int (WINAPI *BassErrorFn)(void);
    BassErrorFn bassError=(BassErrorFn)(ULONG_PTR)GetProcAddress(bass,"BASS_ErrorGetCode");
    if(!bassError)return 29;
    BassInitFn init=(BassInitFn)(ULONG_PTR)GetProcAddress(bass,"BASS_Init");
    if(!init){printf("BASS_INIT missing\\n");fflush(stdout);return 21;}
    if(!init(-1,44100,0,NULL,NULL)){printf("BASS_INIT flags were not forced\\n");fflush(stdout);return 22;}
    if(init(-1,44100,0,NULL,NULL) || bassError()!=14)return 30;
    BassStreamCreateFileFn streamCreate=(BassStreamCreateFileFn)(ULONG_PTR)GetProcAddress(bass,"BASS_StreamCreateFile");
    BassChannelPlayFn channelPlay=(BassChannelPlayFn)(ULONG_PTR)GetProcAddress(bass,"BASS_ChannelPlay");
    BassStreamFreeFn streamFree=(BassStreamFreeFn)(ULONG_PTR)GetProcAddress(bass,"BASS_StreamFree");
    if(!streamCreate||!channelPlay||!streamFree){printf("BASS_DSP API missing\\n");fflush(stdout);return 23;}
    /* Failure paths preserve original result/error; no DSP should attach. */
    if(streamCreate(FALSE,"missing-quote\".ogg",0x100000001ull,0x200000002ull,0) || bassError()!=2)return 31;
    if(streamCreate(FALSE,L"missing-\u97f3\u6548.ogg",0,0,0x80000000u) || bassError()!=2)return 32;
    if(streamCreate(TRUE,(const void*)(uintptr_t)1,0,0,0) || bassError()!=20)return 33;
    if(channelPlay(0,TRUE) || bassError()!=5)return 34;
    /* A 52-byte WAV is recoverable without guessing buffer size. */
    static const unsigned char wave[52]={
        'R','I','F','F',44,0,0,0,'W','A','V','E',
        'f','m','t',' ',16,0,0,0,
        1,0,1,0,0x40,0x1f,0,0,0x80,0x3e,0,0,2,0,16,0,
        'd','a','t','a',8,0,0,0,0,0,0,0,0,0,0
    };
    DWORD recovered=streamCreate(TRUE,wave,0,0,0);
    if(!recovered)return 36;
    if(!channelPlay(recovered,FALSE)||!streamFree(recovered))return 37;
    HANDLE resource=CreateFileW(L"fixture.raw",GENERIC_WRITE,0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(resource==INVALID_HANDLE_VALUE)return 35;
    DWORD written;WriteFile(resource,pcm,sizeof(pcm),&written,NULL);CloseHandle(resource);
    DWORD stream=streamCreate(FALSE,"fixture.raw",0,0,0);
    if(!stream){printf("BASS_STREAM create failed\\n");fflush(stdout);return 24;}
    if(!channelPlay(stream,FALSE)){printf("BASS_STREAM play failed\\n");fflush(stdout);return 25;}
    if(!streamFree(stream)){printf("BASS_STREAM free failed\\n");fflush(stdout);return 26;}
    BassTestFn test=(BassTestFn)(ULONG_PTR)GetProcAddress(bass,"BASS_Test");
    if(!test){printf("BASS_TEST missing\\n");fflush(stdout);return 27;}
    int bassResult=test();
    printf("BASS_TEST result=%d\\n",bassResult);fflush(stdout);
    if(bassResult!=77)return bassResult?bassResult:28;
    /* Run through AISound's dynamic exports and resource.irf with both ABIs
       unmodified: diagnostics must not corrupt the return value or stack. */
    HMODULE ai=LoadLibraryA("aisound.dll");
    if(!ai)return 41;
    Sleep(240);
    typedef int (__cdecl *AiTestFn)(int);
    typedef int (WINAPI *AiInitFn)(int);
    AiInitFn aiInit=(AiInitFn)(ULONG_PTR)GetProcAddress(ai,"InitTTS");
    AiTestFn aiSpeak=(AiTestFn)(ULONG_PTR)GetProcAddress(ai,"Speak");
    if(!aiInit||!aiSpeak)return 42;
    if(aiInit(2)!=42)return 43;
    Sleep(240);
    if(aiSpeak(3)!=43)return 44;
    typedef int (__cdecl *AiVoiceFn)(void);
    typedef int (WINAPI *AiParamFn)(int,int);
    AiVoiceFn getVoiceCount=(AiVoiceFn)(ULONG_PTR)GetProcAddress(ai,"GetVoiceCount");
    AiParamFn setParam=(AiParamFn)(ULONG_PTR)GetProcAddress(ai,"SetParam");
    if(!getVoiceCount || !setParam)return 45;
    if(getVoiceCount()!=7)return 46;
    if(setParam(4,3)!=43)return 47;
    Sleep(250);
    return 0;
}
