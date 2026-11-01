/* SPDX-License-Identifier: MIT. CI only: verify the PID-scoped probe catches early static and dynamic audio routes. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <mmsystem.h>
#include <stdio.h>

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
    typedef int (__cdecl *BassTestFn)(void);
    BassInitFn init=(BassInitFn)(ULONG_PTR)GetProcAddress(bass,"BASS_Init");
    if(!init){printf("BASS_INIT missing\\n");fflush(stdout);return 21;}
    if(!init(-1,44100,0,NULL,NULL)){printf("BASS_INIT flags were not forced\\n");fflush(stdout);return 22;}
    BassTestFn test=(BassTestFn)(ULONG_PTR)GetProcAddress(bass,"BASS_Test");
    if(!test){printf("BASS_TEST missing\\n");fflush(stdout);return 23;}
    int bassResult=test();
    printf("BASS_TEST result=%d\\n",bassResult);fflush(stdout);
    if(bassResult!=77)return bassResult?bassResult:24;
    Sleep(250);
    return 0;
}
