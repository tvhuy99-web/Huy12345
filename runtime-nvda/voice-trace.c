/* SPDX-License-Identifier: MIT. Optional PE32 proxy: preserve the original implementation. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <wchar.h>

static HMODULE self, original;
static INIT_ONCE once=INIT_ONCE_STATIC_INIT;
static HANDLE lock;
static LONG sequence;
static DWORD instance;
static wchar_t tracePath[MAX_PATH];

static BOOL CALLBACK initialize(PINIT_ONCE unused,PVOID arg,PVOID *context) {
    (void)unused;(void)arg;(void)context;
    wchar_t path[MAX_PATH],*tail;
    DWORD count=GetModuleFileNameW(self,path,MAX_PATH);
    if(!count || count>=MAX_PATH)return FALSE;
    tail=wcsrchr(path,L'\\');if(!tail)return FALSE;
    if(tail-path>MAX_PATH-32)return FALSE;
    wcscpy(tail+1,L"winlator-voice-original.dll");
    original=LoadLibraryW(path);
    lock=CreateMutexW(NULL,FALSE,NULL);instance=GetTickCount();
    swprintf(tracePath,MAX_PATH,L"C:\\winlator-nvda\\config\\game-voice-%lu.jsonl",(unsigned long)GetCurrentProcessId());
    return original!=NULL;
}

static FARPROC resolve(const char *name) {
    InitOnceExecuteOnce(&once,initialize,NULL,NULL);
    return original?GetProcAddress(original,name):NULL;
}

static void record(const char *name,const char *phase,LONG call,int result,DWORD error,DWORD elapsed,const void *text,int wide) {
    DWORD saved=GetLastError();
    if(!lock){SetLastError(saved);return;}
    DWORD acquired=WaitForSingleObject(lock,10);
    if(acquired!=WAIT_OBJECT_0 && acquired!=WAIT_ABANDONED_0){SetLastError(saved);return;}
    /* Only a bounded length is observed. Never record a game's text, arguments, or pointers. */
    unsigned length=0;
    if(text) {
        if(wide){const wchar_t *s=(const wchar_t*)text;while(length<4096 && s[length])length++;}
        else {const char *s=(const char*)text;while(length<4096 && s[length])length++;}
    }
    char line[768];DWORD fgPid=0;HWND foreground=GetForegroundWindow();
    GetWindowThreadProcessId(foreground,&fgPid);
    int n=snprintf(line,sizeof(line),"{\"event\":\"call\",\"pid\":%lu,\"tid\":%lu,\"instance\":%lu,\"seq\":%ld,\"call\":%ld,\"api\":\"%s\",\"phase\":\"%s\",\"result\":%d,\"lastError\":%lu,\"elapsedMs\":%lu,\"tick\":%lu,\"acp\":%u,\"units\":%u,\"wide\":%s,\"foregroundPid\":%lu}\n",
        (unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId(),(unsigned long)instance,
        (long)InterlockedIncrement(&sequence),(long)call,name,phase,result,(unsigned long)error,
        (unsigned long)elapsed,(unsigned long)GetTickCount(),GetACP(),length,wide?"true":"false",(unsigned long)fgPid);
    HANDLE file=CreateFileW(tracePath,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file!=INVALID_HANDLE_VALUE) {
        DWORD size=GetFileSize(file,NULL),written;
        if(size>60000) {
            char tail[30000];DWORD got=0;
            SetFilePointer(file,-(LONG)sizeof(tail),NULL,FILE_END);ReadFile(file,tail,sizeof(tail),&got,NULL);
            DWORD skip=0;while(skip<got && tail[skip]!='\n')skip++;if(skip<got)skip++;
            SetFilePointer(file,0,NULL,FILE_BEGIN);WriteFile(file,tail+skip,got-skip,&written,NULL);SetEndOfFile(file);
        }
        SetFilePointer(file,0,NULL,FILE_END);
        if(n>0 && (size_t)n<sizeof(line))WriteFile(file,line,(DWORD)n,&written,NULL);
        CloseHandle(file);
    }
    ReleaseMutex(lock);SetLastError(saved);
}

typedef int (__stdcall *Init)(void*,void*);
typedef int (__stdcall *Speak)(const void*);
static LONG callId;
static int init_call(const char *name,void *a,void *b) {
    DWORD saved=GetLastError();Init fn=(Init)(ULONG_PTR)resolve(name);DWORD loadError=fn?0:GetLastError();
    LONG id=InterlockedIncrement(&callId);record(name,"begin",id,0,loadError,0,NULL,0);
    SetLastError(saved);DWORD started=GetTickCount();int result=fn?fn(a,b):0;DWORD error=GetLastError();
    record(name,"end",id,result,error,GetTickCount()-started,NULL,0);SetLastError(error);return result;
}
static int speak_call(const char *name,const void *text,int wide) {
    DWORD saved=GetLastError();Speak fn=(Speak)(ULONG_PTR)resolve(name);DWORD loadError=fn?0:GetLastError();
    LONG id=InterlockedIncrement(&callId);record(name,"begin",id,0,loadError,0,text,wide);
    SetLastError(saved);DWORD started=GetTickCount();int result=fn?fn(text):0;DWORD error=GetLastError();
    record(name,"end",id,result,error,GetTickCount()-started,NULL,wide);SetLastError(error);return result;
}
int __stdcall traceInitA(void *a,void *b){return init_call("xyttsInitA",a,b);}
int __stdcall traceInitW(void *a,void *b){return init_call("xyttsInitW",a,b);}
int __stdcall traceSpeakA(const void *t){return speak_call("xyttsSpeakA",t,0);}
int __stdcall traceSpeakW(const void *t){return speak_call("xyttsSpeakW",t,1);}
int __stdcall traceSpeak2A(const void *t){return speak_call("xyttsSpeak2A",t,0);}
int __stdcall traceSpeak2W(const void *t){return speak_call("xyttsSpeak2W",t,1);}
typedef int (__stdcall *NoArgs)(void);
typedef int (__stdcall *Notify)(void*,void*,void*);
typedef int (__stdcall *OneArg)(void*);
static int no_args(const char *name) {
    DWORD saved=GetLastError();NoArgs fn=(NoArgs)(ULONG_PTR)resolve(name);LONG id=InterlockedIncrement(&callId);
    record(name,"begin",id,0,fn?0:GetLastError(),0,NULL,0);SetLastError(saved);
    DWORD started=GetTickCount();int result=fn?fn():0;DWORD error=GetLastError();
    record(name,"end",id,result,error,GetTickCount()-started,NULL,0);SetLastError(error);return result;
}
int __stdcall traceStop(void){return no_args("xyttsStop");}
int __stdcall tracePause(void){return no_args("xyttsPause");}
int __stdcall traceNotify(void *a,void *b,void *c){
    DWORD saved=GetLastError();Notify fn=(Notify)(ULONG_PTR)resolve("xyttsSetNotify");LONG id=InterlockedIncrement(&callId);
    record("xyttsSetNotify","begin",id,0,fn?0:GetLastError(),0,NULL,0);SetLastError(saved);
    DWORD started=GetTickCount();int result=fn?fn(a,b,c):0;DWORD error=GetLastError();
    record("xyttsSetNotify","end",id,result,error,GetTickCount()-started,NULL,0);SetLastError(error);return result;
}
int __stdcall traceUninit(void *a){
    DWORD saved=GetLastError();OneArg fn=(OneArg)(ULONG_PTR)resolve("xyttsUninit");LONG id=InterlockedIncrement(&callId);
    record("xyttsUninit","begin",id,0,fn?0:GetLastError(),0,NULL,0);SetLastError(saved);
    DWORD started=GetTickCount();int result=fn?fn(a):0;DWORD error=GetLastError();
    record("xyttsUninit","end",id,result,error,GetTickCount()-started,NULL,0);SetLastError(error);return result;
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID unused){
    (void)unused;if(reason==DLL_PROCESS_ATTACH){self=module;DisableThreadLibraryCalls(module);}return TRUE;
}
