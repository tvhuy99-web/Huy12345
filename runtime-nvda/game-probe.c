/* SPDX-License-Identifier: MIT. Read-only PE32 process/window observer; no injection. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

static FILE *out;
static DWORD target;
static unsigned windows;
static unsigned long long number(FILETIME t){return ((unsigned long long)t.dwHighDateTime<<32)|t.dwLowDateTime;}
static void string(const wchar_t *value){
    char utf8[1600];int size=WideCharToMultiByte(CP_UTF8,0,value,-1,utf8,sizeof(utf8),NULL,NULL);
    fputc('"',out);
    for(int i=0;i<size-1;i++){
        unsigned char c=(unsigned char)utf8[i];
        if(c=='"'||c=='\\'){fputc('\\',out);fputc(c,out);}
        else if(c<32)fprintf(out,"\\u%04x",c);else fputc(c,out);
    }
    fputc('"',out);
}
static BOOL CALLBACK window(HWND hwnd,LPARAM unused){
    (void)unused;DWORD pid=0;DWORD tid=GetWindowThreadProcessId(hwnd,&pid);
    if(pid!=target || windows>=8)return TRUE;
    wchar_t kind[128]={0};GetClassNameW(hwnd,kind,128);
    /* Include hidden application windows, exclude IME/tooltips from the timed ping budget. */
    if(!wcscmp(kind,L"IME")||!wcscmp(kind,L"Wine IME")||!wcscmp(kind,L"tooltips_class32")||!wcscmp(kind,L"_EL_HideOwner"))return TRUE;
    if(windows++)fputc(',',out);
    RECT r={0};GetWindowRect(hwnd,&r);DWORD_PTR response=0;
    SetLastError(0);DWORD began=GetTickCount();LRESULT sent=SendMessageTimeoutW(hwnd,WM_NULL,0,0,SMTO_ABORTIFHUNG|SMTO_BLOCK|SMTO_ERRORONEXIT,200,&response);
    DWORD error=GetLastError(),elapsed=GetTickCount()-began;
    fprintf(out,"{\"hwnd\":%lu,\"thread\":%lu,\"class\":",(unsigned long)(ULONG_PTR)hwnd,(unsigned long)tid);string(kind);
    fprintf(out,",\"visible\":%s,\"enabled\":%s,\"style\":%lu,\"exStyle\":%lu,\"rect\":[%ld,%ld,%ld,%ld],\"wmNullDelivered\":%s,\"pingError\":%lu,\"pingMs\":%lu}",
        IsWindowVisible(hwnd)?"true":"false",IsWindowEnabled(hwnd)?"true":"false",
        (unsigned long)GetWindowLongW(hwnd,GWL_STYLE),(unsigned long)GetWindowLongW(hwnd,GWL_EXSTYLE),
        r.left,r.top,r.right,r.bottom,sent?"true":"false",(unsigned long)error,(unsigned long)elapsed);
    return TRUE;
}
int main(int argc,char **argv){
    if(argc!=3 || strlen(argv[2])!=32)return 2;
    for(int i=0;i<32;i++)if(!strchr("0123456789abcdef",argv[2][i]))return 2;
    char *end;target=strtoul(argv[1],&end,10);if(!target||*end)return 2;
    wchar_t destination[MAX_PATH],temporary[MAX_PATH];
    swprintf(destination,MAX_PATH,L"C:\\winlator-nvda\\config\\game-probe-%hs.json",argv[2]);
    swprintf(temporary,MAX_PATH,L"%ls.tmp",destination);out=_wfopen(temporary,L"wb");if(!out)return 3;
    DWORD began=GetTickCount();HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|SYNCHRONIZE,FALSE,target);DWORD openError=process?0:GetLastError();
    FILETIME utc;GetSystemTimeAsFileTime(&utc);
    unsigned long long epoch=(number(utc)-116444736000000000ull)/10000ull;
    fprintf(out,"{\"version\":1,\"id\":\"%s\",\"pid\":%lu,\"observerBits\":32,\"processOpened\":%s,\"openError\":%lu,\"timeMs\":%llu",argv[2],(unsigned long)target,process?"true":"false",(unsigned long)openError,epoch);
    if(process){
        FILETIME created={0},ended={0},kernel={0},user={0};SetLastError(0);BOOL got=GetProcessTimes(process,&created,&ended,&kernel,&user);DWORD error=got?0:GetLastError();
        DWORD code=0;BOOL exitOk=GetExitCodeProcess(process,&code);
        fprintf(out,",\"timesOk\":%s,\"timesError\":%lu,\"creationTime\":%llu,\"kernelTicks\":%llu,\"userTicks\":%llu,\"signaled\":%s,\"exitCode\":%lu",
            got?"true":"false",(unsigned long)error,number(created),number(kernel),number(user),WaitForSingleObject(process,0)==WAIT_OBJECT_0?"true":"false",exitOk?(unsigned long)code:0ul);
    }
    HANDLE snapshot=INVALID_HANDLE_VALUE;
    for(int i=0;i<3;i++){
        snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,target);
        if(snapshot!=INVALID_HANDLE_VALUE || GetLastError()!=ERROR_BAD_LENGTH)break;
        Sleep(10);
    }
    DWORD moduleError=snapshot==INVALID_HANDLE_VALUE?GetLastError():0;
    fprintf(out,",\"moduleSnapshotError\":%lu,\"modules\":[",(unsigned long)moduleError);
    if(snapshot!=INVALID_HANDLE_VALUE){
        MODULEENTRY32W item={0};item.dwSize=sizeof(item);SetLastError(0);BOOL found=Module32FirstW(snapshot,&item);DWORD firstError=found?0:GetLastError();unsigned count=0;
        while(found && count<96){
            if(count++)fputc(',',out);
            BOOL limited=wcslen(item.szModule)>95;item.szModule[95]=0;
            fprintf(out,"{\"name\":");string(item.szModule);
            fprintf(out,",\"base\":%lu,\"bytes\":%lu,\"nameLimited\":%s}",(unsigned long)(ULONG_PTR)item.modBaseAddr,(unsigned long)item.modBaseSize,limited?"true":"false");
            found=Module32NextW(snapshot,&item);
        }
        fprintf(out,"],\"moduleEnumerationError\":%lu,\"modulesLimited\":%s",(unsigned long)firstError,found?"true":"false");CloseHandle(snapshot);
    }else fprintf(out,"]");
    snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0);DWORD threadError=snapshot==INVALID_HANDLE_VALUE?GetLastError():0;
    fprintf(out,",\"threadSnapshotError\":%lu,\"threads\":[",(unsigned long)threadError);
    if(snapshot!=INVALID_HANDLE_VALUE){
        THREADENTRY32 item={0};item.dwSize=sizeof(item);BOOL found=Thread32First(snapshot,&item);unsigned count=0;
        while(found && count<32){
            if(item.th32OwnerProcessID==target){if(count++)fputc(',',out);fprintf(out,"%lu",(unsigned long)item.th32ThreadID);}
            found=Thread32Next(snapshot,&item);
        }
        CloseHandle(snapshot);
    }
    fprintf(out,"],\"windows\":[");SetLastError(0);BOOL enumerated=EnumWindows(window,0);DWORD windowError=enumerated?0:GetLastError();
    fprintf(out,"],\"windowEnumerationOk\":%s,\"windowEnumerationError\":%lu,\"elapsedMs\":%lu}",enumerated?"true":"false",(unsigned long)windowError,(unsigned long)(GetTickCount()-began));
    if(process)CloseHandle(process);
    fclose(out);if(!MoveFileExW(temporary,destination,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))return 4;
    return 0;
}
