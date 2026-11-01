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
    BassInitFn init=(BassInitFn)(ULONG_PTR)GetProcAddress(bass,"BASS_Init");
    if(!init){printf("BASS_INIT missing\\n");fflush(stdout);return 21;}
    if(!init(-1,44100,0,NULL,NULL)){printf("BASS_INIT flags were not forced\\n");fflush(stdout);return 22;}
    BassStreamCreateFileFn streamCreate=(BassStreamCreateFileFn)(ULONG_PTR)GetProcAddress(bass,"BASS_StreamCreateFile");
    BassChannelPlayFn channelPlay=(BassChannelPlayFn)(ULONG_PTR)GetProcAddress(bass,"BASS_ChannelPlay");
    BassStreamFreeFn streamFree=(BassStreamFreeFn)(ULONG_PTR)GetProcAddress(bass,"BASS_StreamFree");
    if(!streamCreate||!channelPlay||!streamFree){printf("BASS_DSP API missing\\n");fflush(stdout);return 23;}
    DWORD stream=streamCreate(FALSE,"fixture.raw",0,0,0);
    if(!stream){printf("BASS_STREAM create failed\\n");fflush(stdout);return 24;}
    if(!channelPlay(stream,FALSE)){printf("BASS_STREAM play failed\\n");fflush(stdout);return 25;}
    if(!streamFree(stream)){printf("BASS_STREAM free failed\\n");fflush(stdout);return 26;}
    BassTestFn test=(BassTestFn)(ULONG_PTR)GetProcAddress(bass,"BASS_Test");
    if(!test){printf("BASS_TEST missing\\n");fflush(stdout);return 27;}
    int bassResult=test();
    printf("BASS_TEST result=%d\\n",bassResult);fflush(stdout);
    if(bassResult!=77)return bassResult?bassResult:28;
    Sleep(250);
    return 0;
}
