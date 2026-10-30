/* SPDX-License-Identifier: MIT. Test-only observer: no activation or termination of game processes. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <tlhelp32.h>
#include <mmsystem.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

static DWORD tracked[32], count;
static unsigned windows_seen;
static int choose_voice,voice_chosen;
static HWND voice_combo,voice_button,voice_radio;
static int voice_index;
static HWND notice_ack;
static void screenshot(void) {
    int width=GetSystemMetrics(SM_CXSCREEN),height=GetSystemMetrics(SM_CYSCREEN);
    int stride=(width*3+3)&~3;
    HDC screen=GetDC(NULL),memory=CreateCompatibleDC(screen);
    HBITMAP bitmap=CreateCompatibleBitmap(screen,width,height);
    HGDIOBJ old=SelectObject(memory,bitmap);
    BitBlt(memory,0,0,width,height,screen,0,0,SRCCOPY);SelectObject(memory,old);
    BITMAPINFO info={0};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=width;
    info.bmiHeader.biHeight=height;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=24;
    void *pixels=calloc((size_t)height,(size_t)stride);
    if(pixels && GetDIBits(screen,bitmap,0,(UINT)height,pixels,&info,DIB_RGB_COLORS)) {
        BITMAPFILEHEADER header={0};header.bfType=0x4d42;header.bfOffBits=sizeof(header)+sizeof(BITMAPINFOHEADER);header.bfSize=header.bfOffBits+(DWORD)(height*stride);
        FILE *file=fopen("C:\\winlator-nvda\\game-screen.bmp","wb");
        if(file) {fwrite(&header,sizeof(header),1,file);fwrite(&info.bmiHeader,sizeof(BITMAPINFOHEADER),1,file);fwrite(pixels,(size_t)stride,(size_t)height,file);fclose(file);}
    }
    free(pixels);DeleteObject(bitmap);DeleteDC(memory);ReleaseDC(NULL,screen);
}
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
static LRESULT message(HWND w,UINT msg,WPARAM wp,LPARAM lp) {
    DWORD_PTR result=0;
    if(!SendMessageTimeoutW(w,msg,wp,lp,SMTO_ABORTIFHUNG,150,&result))return -1;
    return (LRESULT)result;
}
static unsigned long long ticks(FILETIME t) {return ((unsigned long long)t.dwHighDateTime<<32)|t.dwLowDateTime;}
static BOOL CALLBACK window_row(HWND w,LPARAM child) {
    DWORD pid=0;GetWindowThreadProcessId(w,&pid);if(!contains(pid))return TRUE;
    if(windows_seen++>=160)return FALSE;
    WCHAR title[1024]={0},kind[128]={0};GetClassNameW(w,kind,128);
    if(!child || !lstrcmpiW(kind,L"Static") || !lstrcmpiW(kind,L"Button"))GetWindowTextW(w,title,1024);
    if(!lstrcmpiW(kind,L"_EL_Label"))message(w,WM_GETTEXT,1024,(LPARAM)title);
    RECT r={0};GetWindowRect(w,&r);
    printf("{\"event\":\"window\",\"pid\":%lu,\"hwnd\":%llu,\"parent\":%llu,\"child\":%s,\"visible\":%s,\"enabled\":%s,\"foreground\":%s,\"rect\":[%ld,%ld,%ld,%ld],\"class\":",(unsigned long)pid,(unsigned long long)(ULONG_PTR)w,(unsigned long long)(ULONG_PTR)GetParent(w),child?"true":"false",IsWindowVisible(w)?"true":"false",IsWindowEnabled(w)?"true":"false",GetForegroundWindow()==w?"true":"false",r.left,r.top,r.right,r.bottom);
    string(kind);printf(",\"title\":");string(title);printf("}\n");
    if(!lstrcmpiW(kind,L"ListBox") || !lstrcmpiW(kind,L"ComboBox")) {
        int combo=!lstrcmpiW(kind,L"ComboBox");
        LRESULT items=message(w,combo?CB_GETCOUNT:LB_GETCOUNT,0,0);
        LRESULT selected=message(w,combo?CB_GETCURSEL:LB_GETCURSEL,0,0);
        printf("{\"event\":\"items\",\"hwnd\":%llu,\"pid\":%lu,\"count\":%lld,\"selected\":%lld}\n",(unsigned long long)(ULONG_PTR)w,(unsigned long)pid,(long long)items,(long long)selected);
        for(LRESULT i=0;i<items && i<24;i++) {
            LRESULT length=message(w,combo?CB_GETLBTEXTLEN:LB_GETTEXTLEN,(WPARAM)i,0);
            if(length<0 || length>=1024)continue;
            WCHAR text[1024]={0};message(w,combo?CB_GETLBTEXT:LB_GETTEXT,(WPARAM)i,(LPARAM)text);
            printf("{\"event\":\"item\",\"hwnd\":%llu,\"index\":%lld,\"text\":",(unsigned long long)(ULONG_PTR)w,(long long)i);string(text);printf("}\n");
            if(choose_voice && !voice_chosen && combo && IsWindowVisible(w) && wcsstr(text,L"NVDA")) {voice_combo=w;voice_index=(int)i;}
        }
    }
    if(choose_voice && !voice_chosen && !lstrcmpiW(kind,L"Button") && IsWindowVisible(w)) {
        LONG style=GetWindowLongW(w,GWL_STYLE)&15;
        if(wcsstr(title,L"NVDA"))voice_radio=w;
        if(style<=1 && (GetDlgCtrlID(w)==IDOK || !lstrcmpW(title,L"确定") || !lstrcmpiW(title,L"OK")))voice_button=w;
    }
    if(choose_voice && IsWindowVisible(w) && wcsstr(title,L"首次使用本API"))notice_ack=GetAncestor(w,GA_ROOT);
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
    if(notice_ack && IsWindowVisible(notice_ack)) {
        HWND button=GetDlgItem(notice_ack,IDOK);
        if(button)PostMessageW(button,BM_CLICK,0,0);
        printf("{\"event\":\"acknowledgeVoiceSetupNotice\"}\n");notice_ack=NULL;voice_button=NULL;
    }
    if(voice_combo && voice_button && !voice_chosen && GetAncestor(voice_combo,GA_ROOT)==GetAncestor(voice_button,GA_ROOT)) {
        HWND parent=GetParent(voice_combo);int id=GetDlgCtrlID(voice_combo);
        message(voice_combo,CB_SETCURSEL,(WPARAM)voice_index,0);
        message(parent,WM_COMMAND,MAKEWPARAM(id,CBN_SELCHANGE),(LPARAM)voice_combo);
        voice_chosen=1;PostMessageW(voice_button,BM_CLICK,0,0);
        printf("{\"event\":\"chooseVoice\",\"name\":\"NVDA\",\"index\":%d}\n",voice_index);fflush(stdout);
    }
    if(voice_radio && !voice_chosen) {
        message(voice_radio,BM_CLICK,0,0);
        if(voice_button && GetAncestor(voice_radio,GA_ROOT)==GetAncestor(voice_button,GA_ROOT))PostMessageW(voice_button,BM_CLICK,0,0);
        voice_chosen=1;printf("{\"event\":\"chooseVoice\",\"name\":\"NVDA\",\"method\":\"labelled-button\"}\n");fflush(stdout);
    }
}
int main(int argc,char **argv) {
    (void)argv;choose_voice=argc>1;
    SetErrorMode(SEM_FAILCRITICALERRORS);
    printf("{\"event\":\"environment\",\"ansiCodepage\":%u,\"oemCodepage\":%u,\"userLcid\":%lu,\"waveDevices\":%u}\n",GetACP(),GetOEMCP(),(unsigned long)GetUserDefaultLCID(),waveOutGetNumDevs());fflush(stdout);
    WCHAR command[]=L"\"C:\\game\\zetianji.exe\"";
    STARTUPINFOW si={0};PROCESS_INFORMATION p={0};si.cb=sizeof(si);si.dwFlags=STARTF_USESHOWWINDOW;si.wShowWindow=SW_SHOW;
    if(!CreateProcessW(NULL,command,NULL,NULL,FALSE,0,NULL,L"C:\\game",&si,&p)) {
        printf("{\"event\":\"launchFailed\",\"code\":%lu}\n",(unsigned long)GetLastError());return 1;
    }
    CloseHandle(p.hThread);tracked[count++]=p.dwProcessId;
    printf("{\"event\":\"started\",\"pid\":%lu}\n",(unsigned long)p.dwProcessId);fflush(stdout);
    DWORD started=GetTickCount();const DWORD checkpoints[]={1000,4000,10000,20000,30000,40000,60000};
    for(unsigned i=0;i<sizeof(checkpoints)/sizeof(checkpoints[0]);i++) {
        DWORD elapsed=GetTickCount()-started;if(elapsed<checkpoints[i])Sleep(checkpoints[i]-elapsed);
        snapshot(p.hProcess,GetTickCount()-started);
    }
    screenshot();
    CloseHandle(p.hProcess);return 0;
}
