/* SPDX-License-Identifier: MIT. Test-only synthetic AISound/IRF DLLs. */
#include <windows.h>
typedef int (__cdecl *ResourceFn)(int);
#ifdef BUILD_IRF
__declspec(dllexport) int __cdecl aisound_initialize(int value){return value+100;}
__declspec(dllexport) int __cdecl aisound_speak(int value){return value+200;}
#else
static HMODULE resource;
__declspec(dllexport) int __cdecl InitTTS(int value){
    resource=LoadLibraryA("resource.irf");
    if(!resource)return -100;
    /* Deliberate import GetProcAddress call for in-module hook coverage. */
    ResourceFn fn=(ResourceFn)(ULONG_PTR)GetProcAddress(resource,"aisound_initialize");
    if(!fn || fn(11)!=111)return -101;
    return value+40;
}
__declspec(dllexport) int __cdecl Speak(int value){
    if(!resource)return -102;
    ResourceFn fn=(ResourceFn)(ULONG_PTR)GetProcAddress(resource,"aisound_speak");
    if(!fn || fn(12)!=212)return -103;
    return value+40;
}
#endif
