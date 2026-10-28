/* SPDX-License-Identifier: MIT
 * Launch NVDA with valid Windows standard handles. Wine-created GUI processes
 * can inherit invalid handles, which prevents embedded Python from starting.
 */
#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

static HANDLE diagnosis;
static BOOL CALLBACK inspect_window(HWND window, LPARAM child) {
    if (!IsWindowVisible(window)) return TRUE;
    WCHAR text[1024] = {0}; DWORD_PTR result=0;
    SendMessageTimeoutW(window,WM_GETTEXT,1024,(LPARAM)text,SMTO_ABORTIFHUNG,100,&result);
    if(text[0]) {
        char utf8[4096];DWORD written;
        int size=WideCharToMultiByte(CP_UTF8,0,text,-1,utf8,sizeof(utf8),NULL,NULL);
        if(size>0){WriteFile(diagnosis,utf8,size-1,&written,NULL);WriteFile(diagnosis,"\r\n",2,&written,NULL);}
    }
    if(!child)EnumChildWindows(window,inspect_window,1);
    return TRUE;
}

int main(int argc, char **argv) {
    if(argc==2 && !strcmp(argv[1],"diagnose")) {
        diagnosis=CreateFileW(L"C:\\winlator-nvda\\windows.txt",GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_ALWAYS,0,NULL);
        if(diagnosis==INVALID_HANDLE_VALUE)return 3;
        EnumWindows(inspect_window,0);CloseHandle(diagnosis);return 0;
    }
    if (argc != 3 || (strcmp(argv[1],"start") && strcmp(argv[1],"stop") && strcmp(argv[1],"probe"))) return 2;
    const char *directory = argv[2];
    if (strncmp(directory,"runtime-",8) || strlen(directory)>80 || strspn(directory,"runtime-0123456789.abcdef")!=strlen(directory)) return 2;
    WCHAR wide[100];
    if (!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,directory,-1,wide,100)) return 2;
    WCHAR binary[256], command[1024];
    swprintf(binary,256,L"C:\\winlator-nvda\\%ls\\nvda.exe",wide);
    const WCHAR *options = !strcmp(argv[1],"stop") ? L"--quit" : !strcmp(argv[1],"probe")
        ? L"-c C:\\winlator-nvda\\config --log-file=C:\\winlator-nvda\\nvda.log --log-level=10"
        : L"-c C:\\winlator-nvda\\config --no-logging";
    swprintf(command,1024,L"\"%ls\" %ls",binary,options);
    SECURITY_ATTRIBUTES inherit = {sizeof(SECURITY_ATTRIBUTES),NULL,TRUE};
    HANDLE input=CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,&inherit,OPEN_EXISTING,0,NULL);
    BOOL probe=!strcmp(argv[1],"probe");
    HANDLE output=CreateFileW(probe ? L"C:\\winlator-nvda\\stdio.txt" : L"NUL",GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,&inherit,probe ? CREATE_ALWAYS:OPEN_EXISTING,0,NULL);
    if(input==INVALID_HANDLE_VALUE || output==INVALID_HANDLE_VALUE) {
        if(input!=INVALID_HANDLE_VALUE)CloseHandle(input);
        if(output!=INVALID_HANDLE_VALUE)CloseHandle(output);
        return 3;
    }
    STARTUPINFOW startup; PROCESS_INFORMATION process;
    ZeroMemory(&startup,sizeof(startup));startup.cb=sizeof(startup);
    startup.dwFlags=STARTF_USESTDHANDLES;startup.hStdInput=input;startup.hStdOutput=output;startup.hStdError=output;
    BOOL ok=CreateProcessW(binary,command,NULL,NULL,TRUE,0,NULL,NULL,&startup,&process);
    CloseHandle(input);CloseHandle(output);
    if(!ok)return 4;
    CloseHandle(process.hThread);
    DWORD result=0;
    if(!strcmp(argv[1],"probe")) {
        if(WaitForSingleObject(process.hProcess,90000)==WAIT_OBJECT_0)GetExitCodeProcess(process.hProcess,&result);
    }
    CloseHandle(process.hProcess);return (int)result;
}
