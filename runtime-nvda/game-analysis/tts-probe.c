/* SPDX-License-Identifier: MIT. Known NVDA Controller API calls, after game observation. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdio.h>
typedef long (__stdcall *Check)(void);
typedef long (__stdcall *Speak)(const wchar_t*);
typedef long (__stdcall *GetNvdaPid)(DWORD*);
typedef long (__stdcall *IsSpeaking)(unsigned char*);
typedef long (__stdcall *SpeakSsml)(const wchar_t*,int,int,unsigned char);
typedef int (__stdcall *ProxyInit)(void*,void*);
typedef int (__stdcall *ProxySpeakW)(const wchar_t*);
typedef int (__stdcall *ProxySpeakA)(const char*);
int main(int argc,char **argv) {
    (void)argv;SetCurrentDirectoryW(L"C:\\game");
    const wchar_t *paths[]={L"C:\\game\\nvdaTTS.dll",L"C:\\game\\vendor\\NVDA\\x86\\nvdaControllerClient.dll"};
    for(unsigned i=0;i<2;i++) {
        HMODULE library=LoadLibraryW(paths[i]);
        printf("{\"client\":%u,\"loaded\":%s,\"loadError\":%lu}\n",i,library?"true":"false",library?0ul:(unsigned long)GetLastError());fflush(stdout);
        if(!library)continue;
        Check check=(Check)(ULONG_PTR)GetProcAddress(library,"nvdaController_testIfRunning");
        Speak speak=(Speak)(ULONG_PTR)GetProcAddress(library,"nvdaController_speakText");
        GetNvdaPid getpid=(GetNvdaPid)(ULONG_PTR)GetProcAddress(library,"nvdaController_getProcessId");
        IsSpeaking speaking=(IsSpeaking)(ULONG_PTR)GetProcAddress(library,"nvdaController_isSpeaking");
        SpeakSsml ssml=(SpeakSsml)(ULONG_PTR)GetProcAddress(library,"nvdaController_speakSsml");
        if(getpid) {DWORD pid=0;long status=getpid(&pid);printf("{\"client\":%u,\"pidResult\":%ld,\"nvdaPid\":%lu}\n",i,status,(unsigned long)pid);fflush(stdout);}
        if(speaking) {unsigned char active=0;long status=speaking(&active);printf("{\"client\":%u,\"speakingResult\":%ld,\"isSpeaking\":%d}\n",i,status,(int)active);fflush(stdout);}
        if(check) {
            long result=check();printf("{\"client\":%u,\"runningResult\":%ld}\n",i,result);fflush(stdout);
            if(result==0 && speak) {result=speak(L"Kiểm tra kết nối thư viện game với NVDA.");printf("{\"client\":%u,\"speakResult\":%ld}\n",i,result);fflush(stdout);}
        }
        if(ssml) {
            long status=ssml(L"<speak>Kiểm tra lời đọc SSML.</speak>",-1,0,1);
            printf("{\"client\":%u,\"ssmlAsyncResult\":%ld}\n",i,status);fflush(stdout);
            printf("{\"client\":%u,\"ssmlSyncBegin\":true}\n",i);fflush(stdout);
            status=ssml(L"<speak>Kiểm tra hoàn tất lời đọc.</speak>",-1,0,0);
            printf("{\"client\":%u,\"ssmlSyncResult\":%ld}\n",i,status);fflush(stdout);
        }
        FreeLibrary(library);
    }
    if(argc>1) {
        HMODULE library=LoadLibraryW(L"C:\\game\\xinyitts.dll");
        ProxyInit init=library?(ProxyInit)(ULONG_PTR)GetProcAddress(library,"xyttsInitA"):NULL;
        ProxySpeakW wide=library?(ProxySpeakW)(ULONG_PTR)GetProcAddress(library,"xyttsSpeakW"):NULL;
        ProxySpeakA ansi=library?(ProxySpeakA)(ULONG_PTR)GetProcAddress(library,"xyttsSpeakA"):NULL;
        printf("{\"proxyLoaded\":%s}\n",library?"true":"false");fflush(stdout);
        if(init) {int status=init(NULL,NULL);printf("{\"proxyInitResult\":%d}\n",status);fflush(stdout);}
        if(wide) {int status=wide(L"Kiểm tra trực tiếp bộ chuyển giọng.");printf("{\"proxySpeakWResult\":%d}\n",status);fflush(stdout);}
        Sleep(1000);
        if(ansi) {int status=ansi("Voice adapter ASCII check.");printf("{\"proxySpeakAResult\":%d}\n",status);fflush(stdout);}
        Sleep(1000);
        if(library)FreeLibrary(library);
    }
    return 0;
}
