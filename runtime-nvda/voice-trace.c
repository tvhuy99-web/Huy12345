/* SPDX-License-Identifier: MIT. Optional PE32 proxy: preserve the original implementation. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <mmsystem.h>
#include <stdio.h>
#include <stdint.h>
#include <wchar.h>
#include <string.h>

static HMODULE self, original;
static INIT_ONCE once=INIT_ONCE_STATIC_INIT;
static HANDLE lock;
static LONG sequence;
static DWORD instance;
static wchar_t tracePath[MAX_PATH];
static void record(const char*,const char*,LONG,int,DWORD,DWORD,const void*,int);


typedef struct {
    LONG calls;
    unsigned long long bytes;
    unsigned long long sampled;
    unsigned long long nonzero;
    DWORD lastLog;
} AUDIO_STAT;

static AUDIO_STAT waveZetianji,waveOpenAL,waveBass,waveAiSound,alBufferDataStat,alSourcePlayStat;
typedef MMRESULT (WINAPI *WaveOutWriteFn)(HWAVEOUT,LPWAVEHDR,UINT);
typedef void (__cdecl *AlBufferDataFn)(unsigned int,int,const void*,int,int);
typedef void (__cdecl *AlSourcePlayFn)(unsigned int);
static WaveOutWriteFn realWaveOutWrite;
static AlBufferDataFn realAlBufferData;
static AlSourcePlayFn realAlSourcePlay;

static BOOL readable_range(const void *address,SIZE_T bytes){
    if(!address || !bytes)return FALSE;
    MEMORY_BASIC_INFORMATION info;
    if(!VirtualQuery(address,&info,sizeof(info)) || info.State!=MEM_COMMIT || (info.Protect&PAGE_GUARD)
       || (info.Protect&0xff)==PAGE_NOACCESS)return FALSE;
    uintptr_t start=(uintptr_t)address,end=(uintptr_t)info.BaseAddress+info.RegionSize;
    return start<=end && bytes<=end-start;
}
static SIZE_T sample_nonzero(const void *data,SIZE_T bytes,SIZE_T *sampled){
    const SIZE_T cap=1024u*1024u;
    SIZE_T wanted=bytes<cap?bytes:cap,done=0,nonzero=0;
    const unsigned char *cursor=(const unsigned char*)data;
    while(done<wanted){
        MEMORY_BASIC_INFORMATION info;
        if(!VirtualQuery(cursor+done,&info,sizeof(info)) || info.State!=MEM_COMMIT || (info.Protect&PAGE_GUARD)
           || (info.Protect&0xff)==PAGE_NOACCESS)break;
        uintptr_t at=(uintptr_t)(cursor+done),end=(uintptr_t)info.BaseAddress+info.RegionSize;
        if(end<=at)break;
        SIZE_T chunk=end-at<wanted-done?end-at:wanted-done;
        for(SIZE_T i=0;i<chunk;i++)if(cursor[done+i])nonzero++;
        done+=chunk;
    }
    *sampled=done;return nonzero;
}
static void write_audio_line_locked(const char *line,int n){
    HANDLE file=CreateFileW(tracePath,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                            NULL,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE)return;
    DWORD size=GetFileSize(file,NULL),written;
    if(size>60000){
        char tail[30000];DWORD got=0;
        SetFilePointer(file,-(LONG)sizeof(tail),NULL,FILE_END);ReadFile(file,tail,sizeof(tail),&got,NULL);
        DWORD skip=0;while(skip<got && tail[skip]!='\n')skip++;if(skip<got)skip++;
        SetFilePointer(file,0,NULL,FILE_BEGIN);WriteFile(file,tail+skip,got-skip,&written,NULL);SetEndOfFile(file);
    }
    SetFilePointer(file,0,NULL,FILE_END);
    if(n>0)WriteFile(file,line,(DWORD)n,&written,NULL);
    CloseHandle(file);
}
static void record_audio(AUDIO_STAT *state,const char *api,const char *source,SIZE_T bytes,SIZE_T sampled,
                         SIZE_T nonzero,int format,int rate,int result){
    DWORD saved=GetLastError();
    if(!lock){SetLastError(saved);return;}
    DWORD acquired=WaitForSingleObject(lock,10);
    if(acquired!=WAIT_OBJECT_0 && acquired!=WAIT_ABANDONED_0){SetLastError(saved);return;}
    LONG call=++state->calls;state->bytes+=bytes;state->sampled+=sampled;state->nonzero+=nonzero;
    DWORD now=GetTickCount();BOOL firstSignal=nonzero && state->nonzero==nonzero;
    if(call<=8 || now-state->lastLog>=1000 || firstSignal){
        state->lastLog=now;
        FILETIME utc;GetSystemTimeAsFileTime(&utc);
        unsigned long long epoch=((((unsigned long long)utc.dwHighDateTime<<32)|utc.dwLowDateTime)-116444736000000000ull)/10000ull;
        char line[1024];
        int n=snprintf(line,sizeof(line),
            "{\"event\":\"audio\",\"pid\":%lu,\"tid\":%lu,\"instance\":%lu,\"seq\":%ld,\"api\":\"%s\",\"source\":\"%s\","
            "\"call\":%ld,\"bytes\":%llu,\"sampledBytes\":%llu,\"nonZeroBytes\":%llu,\"limited\":%s,"
            "\"totalBytes\":%llu,\"totalSampledBytes\":%llu,\"totalNonZeroBytes\":%llu,\"format\":%d,\"rate\":%d,"
            "\"result\":%d,\"tick\":%lu,\"timeMs\":%llu}\n",
            (unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId(),(unsigned long)instance,
            (long)InterlockedIncrement(&sequence),api,source,(long)call,(unsigned long long)bytes,
            (unsigned long long)sampled,(unsigned long long)nonzero,bytes>sampled?"true":"false",
            state->bytes,state->sampled,state->nonzero,format,rate,result,(unsigned long)now,epoch);
        if(n>0 && (size_t)n<sizeof(line))write_audio_line_locked(line,n);
    }
    ReleaseMutex(lock);SetLastError(saved);
}
typedef struct {
    BOOL moduleFound;
    BOOL peValid;
    BOOL importTableFound;
    BOOL importDllFound;
    BOOL nameTableFound;
    BOOL importNameFound;
    BOOL originalReady;
    unsigned slots;
    unsigned patches;
    unsigned alreadyPatched;
    unsigned writeFailures;
} HOOK_RESULT;
typedef struct {
    BOOL seen;
    BOOL done;
    HOOK_RESULT last;
} HOOK_STATE;

static int ascii_equal_ci(char a,char b){
    if(a>='A' && a<='Z')a=(char)(a-'A'+'a');
    if(b>='A' && b<='Z')b=(char)(b-'A'+'a');
    return a==b;
}
static BOOL image_ascii_equals(const unsigned char *base,DWORD image,DWORD rva,const char *wanted,BOOL ignoreCase){
    if(!base || !wanted || rva>=image)return FALSE;
    size_t i=0;
    for(;wanted[i];i++){
        if(i>4096 || rva+i>=image)return FALSE;
        char got=(char)base[rva+i];
        if(!got || (ignoreCase?!ascii_equal_ci(got,wanted[i]):got!=wanted[i]))return FALSE;
    }
    return rva+i<image && base[rva+i]==0;
}
static BOOL hook_result_equal(const HOOK_RESULT *a,const HOOK_RESULT *b){
    return a->moduleFound==b->moduleFound && a->peValid==b->peValid
        && a->importTableFound==b->importTableFound && a->importDllFound==b->importDllFound
        && a->nameTableFound==b->nameTableFound && a->importNameFound==b->importNameFound
        && a->originalReady==b->originalReady && a->slots==b->slots && a->patches==b->patches
        && a->alreadyPatched==b->alreadyPatched && a->writeFailures==b->writeFailures;
}
static void record_audio_hook(const char *source,const char *importDll,const char *api,unsigned attempt,const HOOK_RESULT *result){
    DWORD saved=GetLastError();
    if(!lock){SetLastError(saved);return;}
    DWORD acquired=WaitForSingleObject(lock,10);
    if(acquired!=WAIT_OBJECT_0 && acquired!=WAIT_ABANDONED_0){SetLastError(saved);return;}
    char line[1024];FILETIME utc;GetSystemTimeAsFileTime(&utc);
    unsigned long long epoch=((((unsigned long long)utc.dwHighDateTime<<32)|utc.dwLowDateTime)-116444736000000000ull)/10000ull;
    int n=snprintf(line,sizeof(line),
        "{\"event\":\"audio-hook\",\"pid\":%lu,\"tid\":%lu,\"instance\":%lu,\"seq\":%ld,"
        "\"source\":\"%s\",\"importDll\":\"%s\",\"api\":\"%s\",\"attempt\":%u,"
        "\"moduleFound\":%s,\"peValid\":%s,\"importTableFound\":%s,\"importDllFound\":%s,"
        "\"nameTableFound\":%s,\"importNameFound\":%s,\"originalReady\":%s,"
        "\"slots\":%u,\"patches\":%u,\"alreadyPatched\":%u,\"writeFailures\":%u,"
        "\"tick\":%lu,\"timeMs\":%llu}\n",
        (unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId(),(unsigned long)instance,
        (long)InterlockedIncrement(&sequence),source,importDll,api,attempt,
        result->moduleFound?"true":"false",result->peValid?"true":"false",
        result->importTableFound?"true":"false",result->importDllFound?"true":"false",
        result->nameTableFound?"true":"false",result->importNameFound?"true":"false",
        result->originalReady?"true":"false",result->slots,result->patches,result->alreadyPatched,result->writeFailures,
        (unsigned long)GetTickCount(),epoch);
    if(n>0 && (size_t)n<sizeof(line))write_audio_line_locked(line,n);
    ReleaseMutex(lock);SetLastError(saved);
}
static MMRESULT wave_out_write_common(const char *source,AUDIO_STAT *state,HWAVEOUT handle,LPWAVEHDR header,UINT bytes){
    DWORD saved=GetLastError();WAVEHDR copy;SIZE_T sampled=0,nonzero=0,length=0;
    if(readable_range(header,sizeof(copy))){
        memcpy(&copy,header,sizeof(copy));length=copy.dwBufferLength;
        if(copy.lpData && length)nonzero=sample_nonzero(copy.lpData,length,&sampled);
    }
    SetLastError(saved);MMRESULT result=realWaveOutWrite?realWaveOutWrite(handle,header,bytes):MMSYSERR_ERROR;DWORD error=GetLastError();
    record_audio(state,"waveOutWrite",source,length,sampled,nonzero,0,0,(int)result);SetLastError(error);return result;
}
static MMRESULT WINAPI traceWaveZetianji(HWAVEOUT h,LPWAVEHDR p,UINT n){return wave_out_write_common("zetianji.exe",&waveZetianji,h,p,n);}
static MMRESULT WINAPI traceWaveOpenAL(HWAVEOUT h,LPWAVEHDR p,UINT n){return wave_out_write_common("OpenAL32.dll",&waveOpenAL,h,p,n);}
static MMRESULT WINAPI traceWaveBass(HWAVEOUT h,LPWAVEHDR p,UINT n){return wave_out_write_common("bass.dll",&waveBass,h,p,n);}
static MMRESULT WINAPI traceWaveAiSound(HWAVEOUT h,LPWAVEHDR p,UINT n){return wave_out_write_common("aisound.dll",&waveAiSound,h,p,n);}
static void __cdecl traceAlBufferData(unsigned int buffer,int format,const void *data,int size,int rate){
    DWORD saved=GetLastError();SIZE_T bytes=size>0?(SIZE_T)size:0,sampled=0,nonzero=0;
    if(data && bytes)nonzero=sample_nonzero(data,bytes,&sampled);
    SetLastError(saved);if(realAlBufferData)realAlBufferData(buffer,format,data,size,rate);DWORD error=GetLastError();
    record_audio(&alBufferDataStat,"alBufferData","Sound3D.dll",bytes,sampled,nonzero,format,rate,-1);SetLastError(error);
}
static void __cdecl traceAlSourcePlay(unsigned int source){
    DWORD saved=GetLastError();SetLastError(saved);if(realAlSourcePlay)realAlSourcePlay(source);DWORD error=GetLastError();
    record_audio(&alSourcePlayStat,"alSourcePlay","Sound3D.dll",0,0,0,0,0,-1);SetLastError(error);
}
static HOOK_RESULT patch_import_name(HMODULE module,const char *wantedDll,const char *wantedApi,
                                     FARPROC replacement,BOOL originalReady){
    HOOK_RESULT out={0};out.moduleFound=module!=NULL;out.originalReady=originalReady;
    if(!module || !wantedDll || !wantedApi || !replacement)return out;
    unsigned char *base=(unsigned char*)module;IMAGE_DOS_HEADER *dos=(IMAGE_DOS_HEADER*)base;
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<=0)return out;
    IMAGE_NT_HEADERS32 *nt=(IMAGE_NT_HEADERS32*)(base+dos->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC)return out;
    out.peValid=TRUE;
    if(nt->OptionalHeader.NumberOfRvaAndSizes<=IMAGE_DIRECTORY_ENTRY_IMPORT)return out;
    DWORD image=nt->OptionalHeader.SizeOfImage;
    IMAGE_DATA_DIRECTORY directory=nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if(!image || !directory.VirtualAddress || directory.VirtualAddress>=image)return out;
    out.importTableFound=TRUE;
    for(unsigned d=0;d<128;d++){
        DWORD descriptorRva=directory.VirtualAddress+d*(DWORD)sizeof(IMAGE_IMPORT_DESCRIPTOR);
        if(descriptorRva>image-sizeof(IMAGE_IMPORT_DESCRIPTOR))break;
        IMAGE_IMPORT_DESCRIPTOR *entry=(IMAGE_IMPORT_DESCRIPTOR*)(base+descriptorRva);
        if(!entry->Name && !entry->FirstThunk && !entry->OriginalFirstThunk)break;
        if(!entry->Name || !image_ascii_equals(base,image,entry->Name,wantedDll,TRUE))continue;
        out.importDllFound=TRUE;
        if(!entry->OriginalFirstThunk || !entry->FirstThunk
           || entry->OriginalFirstThunk>=image || entry->FirstThunk>=image)continue;
        out.nameTableFound=TRUE;
        for(unsigned i=0;i<4096;i++){
            DWORD nameThunkRva=entry->OriginalFirstThunk+i*(DWORD)sizeof(IMAGE_THUNK_DATA32);
            DWORD iatThunkRva=entry->FirstThunk+i*(DWORD)sizeof(IMAGE_THUNK_DATA32);
            if(nameThunkRva>image-sizeof(IMAGE_THUNK_DATA32) || iatThunkRva>image-sizeof(IMAGE_THUNK_DATA32))break;
            IMAGE_THUNK_DATA32 *nameThunk=(IMAGE_THUNK_DATA32*)(base+nameThunkRva);
            IMAGE_THUNK_DATA32 *iatThunk=(IMAGE_THUNK_DATA32*)(base+iatThunkRva);
            DWORD nameRva=nameThunk->u1.AddressOfData;
            if(!nameRva)break;
            if(IMAGE_SNAP_BY_ORDINAL32(nameRva))continue;
            if(nameRva>image-2 || !image_ascii_equals(base,image,nameRva+2,wantedApi,FALSE))continue;
            out.importNameFound=TRUE;out.slots++;
            DWORD replacement32=(DWORD)(uintptr_t)replacement;
            if(iatThunk->u1.Function==replacement32){out.alreadyPatched++;continue;}
            if(!originalReady)continue;
            DWORD oldProtect=0;
            if(!VirtualProtect(&iatThunk->u1.Function,sizeof(iatThunk->u1.Function),PAGE_READWRITE,&oldProtect)){
                out.writeFailures++;continue;
            }
            iatThunk->u1.Function=replacement32;
            DWORD unusedProtect=0;
            if(!VirtualProtect(&iatThunk->u1.Function,sizeof(iatThunk->u1.Function),oldProtect,&unusedProtect))
                out.writeFailures++;
            else
                out.patches++;
        }
    }
    return out;
}
static void patch_one_name(HOOK_STATE *state,HMODULE module,const char *source,const char *importDll,const char *api,
                           FARPROC replacement,BOOL originalReady,unsigned attempt){
    if(state->done)return;
    HOOK_RESULT result=patch_import_name(module,importDll,api,replacement,originalReady);
    BOOL changed=!state->seen || !hook_result_equal(&state->last,&result);
    if(changed)record_audio_hook(source,importDll,api,attempt,&result);
    state->seen=TRUE;state->last=result;
    if(result.importNameFound && (result.patches || result.alreadyPatched) && result.writeFailures==0)state->done=TRUE;
}
static DWORD WINAPI audio_hook_thread(void *unused){
    (void)unused;HMODULE pin=NULL;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,(LPCWSTR)(ULONG_PTR)&audio_hook_thread,&pin);
    HOOK_STATE zetWave={0},openalWave={0},bassWave={0},aiWave={0},soundBuffer={0},soundPlay={0};
    for(unsigned attempt=0;attempt<240;attempt++){
        HMODULE winmm=GetModuleHandleW(L"winmm.dll");
        if(winmm && !realWaveOutWrite)
            realWaveOutWrite=(WaveOutWriteFn)(ULONG_PTR)GetProcAddress(winmm,"waveOutWrite");
        patch_one_name(&zetWave,GetModuleHandleW(NULL),"zetianji.exe","WINMM.dll","waveOutWrite",
                       (FARPROC)(ULONG_PTR)traceWaveZetianji,realWaveOutWrite!=NULL,attempt);
        patch_one_name(&openalWave,GetModuleHandleW(L"OpenAL32.dll"),"OpenAL32.dll","WINMM.dll","waveOutWrite",
                       (FARPROC)(ULONG_PTR)traceWaveOpenAL,realWaveOutWrite!=NULL,attempt);
        patch_one_name(&bassWave,GetModuleHandleW(L"bass.dll"),"bass.dll","WINMM.dll","waveOutWrite",
                       (FARPROC)(ULONG_PTR)traceWaveBass,realWaveOutWrite!=NULL,attempt);
        patch_one_name(&aiWave,GetModuleHandleW(L"aisound.dll"),"aisound.dll","WINMM.dll","waveOutWrite",
                       (FARPROC)(ULONG_PTR)traceWaveAiSound,realWaveOutWrite!=NULL,attempt);
        HMODULE openal=GetModuleHandleW(L"OpenAL32.dll");
        if(openal && !realAlBufferData)realAlBufferData=(AlBufferDataFn)(ULONG_PTR)GetProcAddress(openal,"alBufferData");
        if(openal && !realAlSourcePlay)realAlSourcePlay=(AlSourcePlayFn)(ULONG_PTR)GetProcAddress(openal,"alSourcePlay");
        HMODULE sound=GetModuleHandleW(L"Sound3D.dll");
        patch_one_name(&soundBuffer,sound,"Sound3D.dll","OpenAL32.dll","alBufferData",
                       (FARPROC)(ULONG_PTR)traceAlBufferData,realAlBufferData!=NULL,attempt);
        patch_one_name(&soundPlay,sound,"Sound3D.dll","OpenAL32.dll","alSourcePlay",
                       (FARPROC)(ULONG_PTR)traceAlSourcePlay,realAlSourcePlay!=NULL,attempt);
        Sleep(250);
    }
    return 0;
}

static BOOL CALLBACK initialize(PINIT_ONCE unused,PVOID arg,PVOID *context) {
    (void)unused;(void)arg;(void)context;
    wchar_t path[MAX_PATH],*tail;
    DWORD count=GetModuleFileNameW(self,path,MAX_PATH);
    if(!count || count>=MAX_PATH)return FALSE;
    tail=wcsrchr(path,L'\\');if(!tail)return FALSE;
    if(tail-path>MAX_PATH-32)return FALSE;
    wcscpy(tail+1,L"winlator-voice-original.dll");
    lock=CreateMutexW(NULL,FALSE,NULL);instance=GetTickCount();
    swprintf(tracePath,MAX_PATH,L"C:\\winlator-nvda\\config\\game-voice-%lu.jsonl",(unsigned long)GetCurrentProcessId());
    record("proxy.loadOriginal","begin",0,0,0,0,NULL,0);
    DWORD began=GetTickCount();SetLastError(0);original=LoadLibraryW(path);DWORD error=original?0:GetLastError();
    record("proxy.loadOriginal","end",0,original!=NULL,error,GetTickCount()-began,NULL,0);
    if(original){HANDLE thread=CreateThread(NULL,0,audio_hook_thread,NULL,0,NULL);if(thread)CloseHandle(thread);}
    return original!=NULL;
}

static FARPROC resolve(const char *name) {
    InitOnceExecuteOnce(&once,initialize,NULL,NULL);
    FARPROC fn=original?GetProcAddress(original,name):NULL;
    if(!fn)record(name,"missing-export",0,0,GetLastError(),0,NULL,0);
    return fn;
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
    FILETIME utc;GetSystemTimeAsFileTime(&utc);
    unsigned long long epoch=((((unsigned long long)utc.dwHighDateTime<<32)|utc.dwLowDateTime)-116444736000000000ull)/10000ull;
    int defined=strcmp(name,"xyttsSetNotify") && strcmp(name,"xyttsUninit");
    int n=snprintf(line,sizeof(line),"{\"event\":\"call\",\"pid\":%lu,\"tid\":%lu,\"instance\":%lu,\"seq\":%ld,\"call\":%ld,\"api\":\"%s\",\"phase\":\"%s\",\"result\":%d,\"resultDefined\":%s,\"lastError\":%lu,\"elapsedMs\":%lu,\"tick\":%lu,\"timeMs\":%llu,\"acp\":%u,\"units\":%u,\"wide\":%s,\"foregroundPid\":%lu}\n",
        (unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId(),(unsigned long)instance,
        (long)InterlockedIncrement(&sequence),(long)call,name,phase,result,defined?"true":"false",(unsigned long)error,
        (unsigned long)elapsed,(unsigned long)GetTickCount(),epoch,GetACP(),length,wide?"true":"false",(unsigned long)fgPid);
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
