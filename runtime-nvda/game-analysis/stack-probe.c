/* SPDX-License-Identifier: MIT. Same-bitness, bounded thread snapshots in the disposable test prefix. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>
static HANDLE process;
static void address(DWORD value) {
    MEMORY_BASIC_INFORMATION info={0};
    if(VirtualQueryEx(process,(void*)(ULONG_PTR)value,&info,sizeof(info)) && (info.Protect&(PAGE_EXECUTE|PAGE_EXECUTE_READ|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY)))printf(" %08lx",(unsigned long)value);
}
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    DWORD pid=(DWORD)strtoul(argv[1],NULL,10);
    process=OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ,FALSE,pid);
    if(!process) {printf("OpenProcess error %lu\n",(unsigned long)GetLastError());return 1;}
    HANDLE modules=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE,pid);
    if(modules!=INVALID_HANDLE_VALUE) {
        MODULEENTRY32W m={0};m.dwSize=sizeof(m);
        if(Module32FirstW(modules,&m))do {
            char name[1024];WideCharToMultiByte(CP_UTF8,0,m.szModule,-1,name,sizeof(name),NULL,NULL);
            printf("MODULE %08lx size=%lu %s\n",(unsigned long)(ULONG_PTR)m.modBaseAddr,(unsigned long)m.modBaseSize,name);
        }while(Module32NextW(modules,&m));CloseHandle(modules);
    }
    HANDLE snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0);
    if(snapshot==INVALID_HANDLE_VALUE)return 1;
    THREADENTRY32 entry={0};entry.dwSize=sizeof(entry);unsigned count=0;
    if(Thread32First(snapshot,&entry))do {
        if(entry.th32OwnerProcessID!=pid || count++>=12)continue;
        HANDLE thread=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT|THREAD_QUERY_INFORMATION,FALSE,entry.th32ThreadID);
        if(!thread)continue;
        CONTEXT context={0};context.ContextFlags=CONTEXT_FULL;
        DWORD suspended=SuspendThread(thread);BOOL got=FALSE;
        if(suspended!=(DWORD)-1) {got=GetThreadContext(thread,&context);ResumeThread(thread);}
        printf("THREAD %lu context=%d error=%lu eip=%08lx esp=%08lx ebp=%08lx\n",(unsigned long)entry.th32ThreadID,(int)got,(unsigned long)GetLastError(),(unsigned long)context.Eip,(unsigned long)context.Esp,(unsigned long)context.Ebp);
        if(got) {
            DWORD words[96]={0};SIZE_T bytes=0;
            if(ReadProcessMemory(process,(void*)(ULONG_PTR)context.Esp,words,sizeof(words),&bytes)) {
                printf("STACK_EXECUTABLE_ADDRESS_CANDIDATES");
                for(SIZE_T i=0;i<bytes/sizeof(DWORD);i++)address(words[i]);
                printf("\n");
            }
        }
        CloseHandle(thread);
    }while(Thread32Next(snapshot,&entry));
    CloseHandle(snapshot);CloseHandle(process);return 0;
}
