/* SPDX-License-Identifier: MIT. CI only. */
#define UNICODE
#include <windows.h>
#include <mmsystem.h>
#include <stdio.h>
typedef int (__stdcall *Init)(void*,void*);
typedef int (__stdcall *SpeakA)(const char*);
typedef int (__stdcall *SpeakW)(const wchar_t*);
typedef int (__stdcall *Notify)(void*,void*,void*);
typedef int (__stdcall *Uninit)(void*);
typedef int (__stdcall *NoArgs)(void);
typedef int (__cdecl *ExerciseAudio)(void);
#define CHECK(test) do {if(!(test)){printf("FAIL line %d error %lu\n",__LINE__,(unsigned long)GetLastError());return 1;}}while(0)
int main(void){
    SetCurrentDirectoryW(L"C:\\Voice Trace Test");HMODULE sound=LoadLibraryW(L"Sound3D.dll");CHECK(sound);
    ExerciseAudio exercise=(ExerciseAudio)(ULONG_PTR)GetProcAddress(sound,"exerciseAudioHook");CHECK(exercise);
    HMODULE lib=LoadLibraryW(L"C:\\Voice Trace Test\\xinyitts.dll");CHECK(lib);
    Init init=(Init)(ULONG_PTR)GetProcAddress(lib,"xyttsInitA");CHECK(init);
    CHECK(init((void*)17,(void*)29)==73);CHECK(GetLastError()==321);
    init=(Init)(ULONG_PTR)GetProcAddress(lib,(const char*)15);CHECK(init);CHECK(init((void*)17,(void*)29)==74);CHECK(GetLastError()==322);
    SpeakA a=(SpeakA)(ULONG_PTR)GetProcAddress(lib,"xyttsSpeakA");CHECK(a);CHECK(a("ASCII")==105);CHECK(GetLastError()==323);
    SpeakW w=(SpeakW)(ULONG_PTR)GetProcAddress(lib,"xyttsSpeakW");CHECK(w);CHECK(w(L"Tiếng Việt 中文")==213);CHECK(GetLastError()==324);
    Notify notify=(Notify)(ULONG_PTR)GetProcAddress(lib,"xyttsSetNotify");CHECK(notify);CHECK(notify((void*)1,(void*)2,(void*)3)==81);
    Uninit uninit=(Uninit)(ULONG_PTR)GetProcAddress(lib,"xyttsUninit");CHECK(uninit);CHECK(uninit((void*)31)==82);
    NoArgs count=(NoArgs)(ULONG_PTR)GetProcAddress(lib,"xyttsGetCount");CHECK(count);CHECK(count()==715);CHECK(GetLastError()==325);
    NoArgs stop=(NoArgs)(ULONG_PTR)GetProcAddress(lib,"xyttsStop");CHECK(stop);CHECK(stop()==715);
    NoArgs pause=(NoArgs)(ULONG_PTR)GetProcAddress(lib,"xyttsPause");CHECK(pause);CHECK(pause()==715);
    for(int i=0;i<1200;i++)CHECK(a("REPEATED")==108);
    Sleep(500);
    char pcm[16]={0,1,0,2,0,3,0,4,0,5,0,6,0,7,0,8};WAVEHDR header={0};
    header.lpData=pcm;header.dwBufferLength=sizeof(pcm);
    waveOutWrite((HWAVEOUT)(ULONG_PTR)1,&header,sizeof(header));
    CHECK(exercise()==77);Sleep(300);
    FreeLibrary(sound);FreeLibrary(lib);puts("PASS: x86 names/ordinals, bounded audio IAT probes, all arguments, Unicode, original results, last-error, forwarders and trace rotation");return 0;
}
