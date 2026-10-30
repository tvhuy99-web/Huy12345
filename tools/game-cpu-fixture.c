/* SPDX-License-Identifier: MIT. Run only the pinned CPU routine with controlled counters. */
#include <windows.h>
#include <stdio.h>
#include <string.h>
static unsigned sleeps,clockReads,idleReads;
static int zero,fail;
static LONG WINAPI query(ULONG kind,void *data,ULONG length,ULONG *returned){
    if(returned)*returned=length;
    memset(data,0,length);
    if(fail)return (LONG)0xc0000001;
    if(kind==0 && length==44){((BYTE*)data)[40]=4;return 0;}
    if(kind==3 && length==32){ULONGLONG time=100000000ull+(++clockReads)*8000000ull;memcpy((BYTE*)data+8,&time,8);return 0;}
    if(kind==2 && length==312){ULONGLONG idle=zero?0:1000000ull+(++idleReads)*4000000ull;memcpy(data,&idle,8);return 0;}
    return (LONG)0xc0000003;
}
static FARPROC WINAPI resolve(HMODULE module,LPCSTR name){
    (void)module;
    if(strcmp(name,"NtQuerySystemInformation"))ExitProcess(71);
    return (FARPROC)query;
}
static void WINAPI sleep_mock(DWORD ms){
    if(ms!=800)ExitProcess(72);
    if(++sleeps>2){puts("ORIGINAL_ZERO_COUNTER_LOOP_REPRODUCED");fflush(stdout);ExitProcess(77);}
}
static void write_memory(BYTE *at,const void *data,SIZE_T bytes){
    DWORD previous;
    if(!VirtualProtect(at,bytes,PAGE_EXECUTE_READWRITE,&previous))ExitProcess(73);
    memcpy(at,data,bytes);FlushInstructionCache(GetCurrentProcess(),at,bytes);
    VirtualProtect(at,bytes,previous,&previous);
}
int main(int argc,char **argv){
    if(argc!=3)return 2;
    zero=!strcmp(argv[2],"zero");fail=!strcmp(argv[2],"failure");
    HMODULE game=LoadLibraryExA(argv[1],NULL,DONT_RESOLVE_DLL_REFERENCES);
    if((ULONG_PTR)game!=0x400000){printf("Unexpected mapped base %p error %lu\n",(void*)game,(unsigned long)GetLastError());return 3;}
    BYTE *base=(BYTE*)game;
    const BYTE version[]={0xb8,1,0,0,0,0xc3};write_memory(base+0x18e8b0,version,sizeof(version));
    FARPROC value=(FARPROC)resolve;write_memory(base+0x1cd2d8,&value,4);
    value=(FARPROC)GetModuleHandleA;write_memory(base+0x1cd2dc,&value,4);
    value=(FARPROC)sleep_mock;write_memory(base+0x1cd310,&value,4);
    BYTE context[64]={0};
    typedef int(__attribute__((thiscall)) *CPU)(void*);
    int result=((CPU)(base+0x18eb40))(context);
    printf("{\"result\":%d,\"sleeps\":%u,\"clockReads\":%u,\"idleReads\":%u}\n",result,sleeps,clockReads,idleReads);
    return 0;
}
