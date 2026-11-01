/* SPDX-License-Identifier: MIT.
 * Narrow x86 diagnostic loader: only loads a caller-selected DLL into a live zetianji.exe.
 */
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <wchar.h>
#include <stdint.h>

static int basename_is_zetianji(const wchar_t *path){
    const wchar_t *name=wcsrchr(path,L'\\');
    name=name?name+1:path;
    return !_wcsicmp(name,L"zetianji.exe");
}
static uintptr_t remote_module_base(DWORD pid,const wchar_t *wanted){
    HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,pid);
    if(snap==INVALID_HANDLE_VALUE)return 0;
    MODULEENTRY32W entry={0};entry.dwSize=sizeof(entry);
    uintptr_t result=0;
    if(Module32FirstW(snap,&entry)){
        do{
            if(!_wcsicmp(entry.szModule,wanted)){result=(uintptr_t)entry.modBaseAddr;break;}
        }while(Module32NextW(snap,&entry));
    }
    CloseHandle(snap);return result;
}
static void result(const char *state,DWORD pid,DWORD error){
    printf("{\"state\":\"%s\",\"pid\":%lu,\"error\":%lu}\n",
           state,(unsigned long)pid,(unsigned long)error);
    fflush(stdout);
}
int wmain(int argc,wchar_t **argv){
    if(argc!=3){result("invalid-arguments",0,ERROR_INVALID_PARAMETER);return 2;}
    wchar_t *end=NULL;unsigned long value=wcstoul(argv[1],&end,10);
    if(!value || !end || *end){result("invalid-pid",0,ERROR_INVALID_PARAMETER);return 3;}
    DWORD pid=(DWORD)value;
    if(GetFileAttributesW(argv[2])==INVALID_FILE_ATTRIBUTES){result("probe-missing",pid,GetLastError());return 4;}

    DWORD access=PROCESS_QUERY_LIMITED_INFORMATION|PROCESS_CREATE_THREAD|PROCESS_VM_OPERATION|PROCESS_VM_WRITE|PROCESS_VM_READ;
    HANDLE process=OpenProcess(access,FALSE,pid);
    if(!process){result("open-failed",pid,GetLastError());return 5;}
    wchar_t image[32768];DWORD chars=(DWORD)(sizeof(image)/sizeof(image[0]));
    if(!QueryFullProcessImageNameW(process,0,image,&chars) || !basename_is_zetianji(image)){
        DWORD error=GetLastError();if(!error)error=ERROR_ACCESS_DENIED;
        result("target-rejected",pid,error);CloseHandle(process);return 6;
    }

    HMODULE localKernel=GetModuleHandleW(L"kernel32.dll");
    FARPROC localLoad=localKernel?GetProcAddress(localKernel,"LoadLibraryW"):NULL;
    uintptr_t remoteKernel=remote_module_base(pid,L"kernel32.dll");
    if(!localKernel || !localLoad || !remoteKernel){
        result("kernel32-unavailable",pid,GetLastError());CloseHandle(process);return 7;
    }
    uintptr_t rva=(uintptr_t)localLoad-(uintptr_t)localKernel;
    LPTHREAD_START_ROUTINE remoteLoad=(LPTHREAD_START_ROUTINE)(remoteKernel+rva);

    SIZE_T bytes=(wcslen(argv[2])+1)*sizeof(wchar_t);
    void *remote=VirtualAllocEx(process,NULL,bytes,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!remote){result("alloc-failed",pid,GetLastError());CloseHandle(process);return 8;}
    SIZE_T written=0;
    if(!WriteProcessMemory(process,remote,argv[2],bytes,&written) || written!=bytes){
        DWORD error=GetLastError();VirtualFreeEx(process,remote,0,MEM_RELEASE);
        result("write-failed",pid,error);CloseHandle(process);return 9;
    }
    HANDLE thread=CreateRemoteThread(process,NULL,0,remoteLoad,remote,0,NULL);
    if(!thread){
        DWORD error=GetLastError();VirtualFreeEx(process,remote,0,MEM_RELEASE);
        result("thread-failed",pid,error);CloseHandle(process);return 10;
    }
    DWORD wait=WaitForSingleObject(thread,3000),exitCode=0;
    if(wait==WAIT_OBJECT_0)GetExitCodeThread(thread,&exitCode);
    DWORD error=(wait==WAIT_OBJECT_0 && exitCode)?ERROR_SUCCESS:(wait==WAIT_TIMEOUT?WAIT_TIMEOUT:GetLastError());
    CloseHandle(thread);VirtualFreeEx(process,remote,0,MEM_RELEASE);CloseHandle(process);
    if(error){result("load-failed",pid,error);return 11;}
    result("loaded",pid,0);return 0;
}
