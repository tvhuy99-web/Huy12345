/* SPDX-License-Identifier: MIT. CI only: verify AppInit loads the audio probe before game code runs. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <mmsystem.h>

int main(void){
    (void)GetForegroundWindow();
    Sleep(700);
    char pcm[16]={0,1,0,2,0,3,0,4,0,5,0,6,0,7,0,8};
    WAVEHDR header={0};
    header.lpData=pcm;
    header.dwBufferLength=sizeof(pcm);
    waveOutWrite((HWAVEOUT)(ULONG_PTR)1,&header,sizeof(header));
    Sleep(250);
    return 0;
}
