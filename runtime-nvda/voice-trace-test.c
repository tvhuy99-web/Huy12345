/* SPDX-License-Identifier: MIT. CI only. */
#define UNICODE
#include <windows.h>
#include <mmsystem.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
typedef int (__stdcall *Init)(void*,void*);
typedef int (__stdcall *SpeakA)(const char*);
typedef int (__stdcall *SpeakW)(const wchar_t*);
typedef int (__stdcall *Notify)(void*,void*,void*);
typedef int (__stdcall *Uninit)(void*);
typedef int (__stdcall *NoArgs)(void);
typedef int (__cdecl *ExerciseAudio)(void);

static MMRESULT WINAPI sentinelWaveOutWrite(HWAVEOUT h,LPWAVEHDR p,UINT n){
    (void)h;(void)p;(void)n;return (MMRESULT)0x3456;
}
static int eq_ci(const char *a,const char *b){
    while(*a && *b){
        char x=*a++,y=*b++;
        if(x>='A'&&x<='Z')x=(char)(x-'A'+'a');
        if(y>='A'&&y<='Z')y=(char)(y-'A'+'a');
        if(x!=y)return 0;
    }
    return *a==0 && *b==0;
}
static int poison_waveout_import(void){
    unsigned char *base=(unsigned char*)GetModuleHandleW(NULL);
    if(!base)return 0;
    IMAGE_DOS_HEADER *dos=(IMAGE_DOS_HEADER*)base;
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE)return 0;
    IMAGE_NT_HEADERS32 *nt=(IMAGE_NT_HEADERS32*)(base+dos->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC)return 0;
    IMAGE_DATA_DIRECTORY dir=nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if(!dir.VirtualAddress)return 0;
    IMAGE_IMPORT_DESCRIPTOR *imports=(IMAGE_IMPORT_DESCRIPTOR*)(base+dir.VirtualAddress);
    for(unsigned d=0;d<128 && imports[d].Name;d++){
        if(!eq_ci((const char*)(base+imports[d].Name),"WINMM.dll") || !imports[d].OriginalFirstThunk)continue;
        IMAGE_THUNK_DATA32 *names=(IMAGE_THUNK_DATA32*)(base+imports[d].OriginalFirstThunk);
        IMAGE_THUNK_DATA32 *iat=(IMAGE_THUNK_DATA32*)(base+imports[d].FirstThunk);
        for(unsigned i=0;i<4096 && names[i].u1.AddressOfData;i++){
            DWORD rva=names[i].u1.AddressOfData;
            if(IMAGE_SNAP_BY_ORDINAL32(rva))continue;
            IMAGE_IMPORT_BY_NAME *named=(IMAGE_IMPORT_BY_NAME*)(base+rva);
            if(strcmp((const char*)named->Name,"waveOutWrite"))continue;
            DWORD oldProtect=0;
            if(!VirtualProtect(&iat[i].u1.Function,sizeof(iat[i].u1.Function),PAGE_READWRITE,&oldProtect))return 0;
            iat[i].u1.Function=(DWORD)(uintptr_t)sentinelWaveOutWrite;
            DWORD unused=0;VirtualProtect(&iat[i].u1.Function,sizeof(iat[i].u1.Function),oldProtect,&unused);
            return 1;
        }
    }
    return 0;
}

#define CHECK(test) do {if(!(test)){printf("FAIL line %d error %lu\n",__LINE__,(unsigned long)GetLastError());return 1;}}while(0)
int main(void){
    SetCurrentDirectoryW(L"C:\\Voice Trace Test");CHECK(poison_waveout_import());
    HMODULE sound=LoadLibraryW(L"Sound3D.dll");CHECK(sound);
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
    FreeLibrary(sound);FreeLibrary(lib);puts("PASS: x86 names/ordinals, name-based audio IAT probes, all arguments, Unicode, original results, last-error, forwarders and trace rotation");return 0;
}
