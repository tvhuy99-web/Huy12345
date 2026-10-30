/* SPDX-License-Identifier: MIT. Run only the pinned CPU routine with controlled counters. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
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
    /* Map only the image bytes at their preferred base. Do not invoke its loader,
       TLS callbacks, imports or entry point; these tests call only the CPU routine. */
    HANDLE file=CreateFileA(argv[1],GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,0,NULL);
    if(file==INVALID_HANDLE_VALUE)return 3;
    DWORD size=GetFileSize(file,NULL),copied=0;BYTE *raw=malloc(size);
    if(!raw || !ReadFile(file,raw,size,&copied,NULL) || copied!=size)return 4;
    CloseHandle(file);
    IMAGE_DOS_HEADER *dos=(IMAGE_DOS_HEADER*)raw;
    IMAGE_NT_HEADERS32 *nt=(IMAGE_NT_HEADERS32*)(raw+dos->e_lfanew);
    BYTE *base=VirtualAlloc((void*)0x400000,nt->OptionalHeader.SizeOfImage,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);
    if(!base){printf("Mapping failed: %lu\n",(unsigned long)GetLastError());return 5;}
    memcpy(base,raw,nt->OptionalHeader.SizeOfHeaders);
    IMAGE_SECTION_HEADER *section=IMAGE_FIRST_SECTION(nt);
    for(unsigned i=0;i<nt->FileHeader.NumberOfSections;i++)
        memcpy(base+section[i].VirtualAddress,raw+section[i].PointerToRawData,section[i].SizeOfRawData);
    free(raw);
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
