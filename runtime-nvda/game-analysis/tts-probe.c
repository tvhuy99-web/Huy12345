/* SPDX-License-Identifier: MIT. Known NVDA Controller API calls, after game observation. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdio.h>
typedef long (__stdcall *Check)(void);
typedef long (__stdcall *Speak)(const wchar_t*);
int main(void) {
    const wchar_t *paths[]={L"C:\\game\\nvdaTTS.dll",L"C:\\game\\vendor\\NVDA\\x86\\nvdaControllerClient.dll"};
    for(unsigned i=0;i<2;i++) {
        HMODULE library=LoadLibraryW(paths[i]);
        printf("{\"client\":%u,\"loaded\":%s,\"loadError\":%lu}\n",i,library?"true":"false",library?0ul:(unsigned long)GetLastError());fflush(stdout);
        if(!library)continue;
        Check check=(Check)(ULONG_PTR)GetProcAddress(library,"nvdaController_testIfRunning");
        Speak speak=(Speak)(ULONG_PTR)GetProcAddress(library,"nvdaController_speakText");
        if(check) {
            long result=check();printf("{\"client\":%u,\"runningResult\":%ld}\n",i,result);fflush(stdout);
            if(result==0 && speak) {result=speak(L"Kiểm tra kết nối thư viện game với NVDA.");printf("{\"client\":%u,\"speakResult\":%ld}\n",i,result);fflush(stdout);}
        }
        FreeLibrary(library);
    }
    return 0;
}
