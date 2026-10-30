/* SPDX-License-Identifier: MIT. Test-only observer: no activation or termination of game processes. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <tlhelp32.h>
#include <mmsystem.h>
#include <stdio.h>
#include <wchar.h>

static DWORD tracked[32], count;
static unsigned windows_seen;
static void string(const WCHAR *text) {
    char utf8[8192];int size=WideCharToMultiByte(CP_UTF8,0,text,-1,utf8,sizeof(utf8),NULL,NULL);
    putchar('"');
    if(size>0)for(int i=0;i<size-1;i++) {
        unsigned char c=(unsigned char)utf8[i];
        if(c=='"'||c=='\\') {putchar('\\');putchar(c);}
        else if(c<32)printf("\\u%04x",c);
        else putchar(c);
    }
    putchar('"');
}
static int contains(DWORD pid) {for(DWORD i=0;i<count;i++)if(tracked[i]==pid)return 1;return 0;}
static unsigned long long ticks(FILETIME t) {return ((unsigned long long)t.dwHighDateTime<<32)|t.dwLowDateTime;}
static BOOL CALLBACK window_row(HWND w,LPARAM child) {
    DWORD pid=0;GetWindowThreadProcessId(w,&pid);if(!contains(pid))return TRUE;
    if(windows_seen++>=160)return FALSE;
    WCHAR title[1024]={0},kind[128]={0};GetClassNameW(w,kind,128);
    if(!child || !lstrcmpiW(kind,L"Static") || !lstrcmpiW(kind,L"Button"))GetWindowTextW(w,title,1024);
    RECT r={0};GetWindowRect(w,&r);
    printf("{\"event\":\"window\",\"pid\":%lu,\"hwnd\":%llu,\"parent\":%llu,\"child\":%s,\"visible\":%s,\"enabled\":%s,\"foreground\":%s,\"rect\":[%ld,%ld,%ld,%ld],\"class\":",(unsigned long)pid,(unsigned long long)(ULONG_PTR)w,(unsigned long long)(ULONG_PTR)GetParent(w),child?"true":"false",IsWindowVisible(w)?"true":"false",IsWindowEnabled(w)?"true":"false",GetForegroundWindow()==w?"true":"false",r.left,r.top,r.right,r.bottom);
    string(kind);printf(",\"title\":");string(title);printf("}\n");
    if(!child)EnumChildWindows(w,window_row,1);
    return TRUE;
}
static void descendants(void) {
    for(unsigned level=0;level<8;level++) {
        DWORD before=count;HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);
        if(snap==INVALID_HANDLE_VALUE)return;
        PROCESSENTRY32W p={0};p.dwSize=sizeof(p);
        if(Process32FirstW(snap,&p))do {
            if(count<32 && contains(p.th32ParentProcessID) && !contains(p.th32ProcessID))tracked[count++]=p.th32ProcessID;
        }while(Process32NextW(snap,&p));
        CloseHandle(snap);if(before==count)break;
    }
}
static void snapshot(HANDLE root,DWORD elapsed) {
    descendants();DWORD code=0;GetExitCodeProcess(root,&code);
    printf("{\"event\":\"snapshot\",\"elapsedMs\":%lu,\"rootState\":\"%s\",\"rootExitCode\":%lu,\"foreground\":%llu}\n",(unsigned long)elapsed,WaitForSingleObject(root,0)==WAIT_OBJECT_0?"exited":"running",(unsigned long)code,(unsigned long long)(ULONG_PTR)GetForegroundWindow());
    for(DWORD i=0;i<count;i++) {
        HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|SYNCHRONIZE,FALSE,tracked[i]);
        FILETIME created={0},ended={0},kernel={0},user={0};DWORD exit=0;
        BOOL valid=process && GetProcessTimes(process,&created,&ended,&kernel,&user);
        if(process)GetExitCodeProcess(process,&exit);
        printf("{\"event\":\"process\",\"pid\":%lu,\"queryable\":%s,\"exitCode\":%lu,\"kernelTicks\":%llu,\"userTicks\":%llu}\n",(unsigned long)tracked[i],valid?"true":"false",(unsigned long)exit,ticks(kernel),ticks(user));
        if(process)CloseHandle(process);
        HANDLE modules=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,tracked[i]);
        if(modules==INVALID_HANDLE_VALUE) {printf("{\"event\":\"moduleError\",\"pid\":%lu,\"code\":%lu}\n",(unsigned long)tracked[i],(unsigned long)GetLastError());continue;}
        MODULEENTRY32W m={0};m.dwSize=sizeof(m);unsigned n=0;
        if(Module32FirstW(modules,&m))do {
            printf("{\"event\":\"module\",\"pid\":%lu,\"base\":%llu,\"name\":",(unsigned long)tracked[i],(unsigned long long)(ULONG_PTR)m.modBaseAddr);string(m.szModule);printf("}\n");
        }while(++n<160 && Module32NextW(modules,&m));
        CloseHandle(modules);
    }
    windows_seen=0;EnumWindows(window_row,0);fflush(stdout);
}
int main(void) {
    SetErrorMode(SEM_FAILCRITICALERRORS);
    printf("{\"event\":\"environment\",\"ansiCodepage\":%u,\"oemCodepage\":%u,\"userLcid\":%lu,\"waveDevices\":%u}\n",GetACP(),GetOEMCP(),(unsigned long)GetUserDefaultLCID(),waveOutGetNumDevs());fflush(stdout);
    WCHAR command[]=L"\"C:\\game\\zetianji.exe\"";
    STARTUPINFOW si={0};PROCESS_INFORMATION p={0};si.cb=sizeof(si);
    if(!CreateProcessW(NULL,command,NULL,NULL,FALSE,0,NULL,L"C:\\game",&si,&p)) {
        printf("{\"event\":\"launchFailed\",\"code\":%lu}\n",(unsigned long)GetLastError());return 1;
    }
    CloseHandle(p.hThread);tracked[count++]=p.dwProcessId;
    printf("{\"event\":\"started\",\"pid\":%lu}\n",(unsigned long)p.dwProcessId);fflush(stdout);
    DWORD started=GetTickCount();const DWORD checkpoints[]={1000,4000,10000,30000,60000};
    for(unsigned i=0;i<sizeof(checkpoints)/sizeof(checkpoints[0]);i++) {
        DWORD elapsed=GetTickCount()-started;if(elapsed<checkpoints[i])Sleep(checkpoints[i]-elapsed);
        snapshot(p.hProcess,GetTickCount()-started);
    }
    CloseHandle(p.hProcess);return 0;
}
