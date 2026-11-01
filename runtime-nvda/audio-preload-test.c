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
    typedef int (__cdecl *BassTestFn)(void);
    BassTestFn test=(BassTestFn)(ULONG_PTR)GetProcAddress(bass,"BASS_Test");
    if(!test || test()!=77)return 21;
    Sleep(250);
    return 0;
}
