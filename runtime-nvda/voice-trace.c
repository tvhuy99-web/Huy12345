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
static INIT_ONCE traceOnce=INIT_ONCE_STATIC_INIT;
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
static AUDIO_STAT directSoundCreateStat,directSoundBufferCreateStat,directSoundBufferUnlockStat,directSoundBufferPlayStat;
typedef MMRESULT (WINAPI *WaveOutWriteFn)(HWAVEOUT,LPWAVEHDR,UINT);
typedef void (__cdecl *AlBufferDataFn)(unsigned int,int,const void*,int,int);
typedef void (__cdecl *AlSourcePlayFn)(unsigned int);
typedef FARPROC (WINAPI *GetProcAddressFn)(HMODULE,LPCSTR);
typedef HMODULE (WINAPI *LoadLibraryAFn)(LPCSTR);
typedef HMODULE (WINAPI *LoadLibraryWFn)(LPCWSTR);
typedef BOOL (WINAPI *BassInitFn)(int,DWORD,DWORD,HWND,const GUID*);
typedef struct {
    DWORD dwSize,dwFlags,dwBufferBytes,dwReserved;
    LPWAVEFORMATEX lpwfxFormat;
    GUID guid3DAlgorithm;
} DSBUFFERDESC_MIN;
typedef HRESULT (WINAPI *DirectSoundCreateFn)(const GUID*,void**,IUnknown*);
typedef HRESULT (WINAPI *DSCreateBufferFn)(void*,const DSBUFFERDESC_MIN*,void**,IUnknown*);
typedef HRESULT (WINAPI *DSBufferUnlockFn)(void*,void*,DWORD,void*,DWORD);
typedef HRESULT (WINAPI *DSBufferPlayFn)(void*,DWORD,DWORD,DWORD);
static WaveOutWriteFn realWaveOutWrite;
static AlBufferDataFn realAlBufferData;
static AlSourcePlayFn realAlSourcePlay;
static GetProcAddressFn realKernelGetProcAddress;
static LoadLibraryAFn realKernelLoadLibraryA;
static LoadLibraryWFn realKernelLoadLibraryW;
static DirectSoundCreateFn realDirectSoundCreate,realDirectSoundCreate8;
static BassInitFn realBassInit;
static AUDIO_STAT bassInitStat;
static CRITICAL_SECTION dsMapLock;
typedef struct {void **vtable;DSCreateBufferFn createBuffer;} DS_VTABLE_ENTRY;
typedef struct {void **vtable;DSBufferUnlockFn unlock;DSBufferPlayFn play;} DS_BUFFER_VTABLE_ENTRY;
typedef struct {void *object;int format;int rate;} DS_BUFFER_OBJECT_ENTRY;
static DS_VTABLE_ENTRY dsVtables[8];
static DS_BUFFER_VTABLE_ENTRY dsBufferVtables[16];
static DS_BUFFER_OBJECT_ENTRY dsBufferObjects[32];
static unsigned dsVtableCount,dsBufferVtableCount,dsBufferObjectCount;
static LONG dynamicLogCount;
static HRESULT WINAPI traceDSCreateSoundBuffer(void*,const DSBUFFERDESC_MIN*,void**,IUnknown*);
static HRESULT WINAPI traceDSBufferUnlock(void*,void*,DWORD,void*,DWORD);
static HRESULT WINAPI traceDSBufferPlay(void*,DWORD,DWORD,DWORD);
static FARPROC WINAPI traceBassGetProcAddress(HMODULE,LPCSTR);
static HMODULE WINAPI traceBassLoadLibraryA(LPCSTR);
static HMODULE WINAPI traceBassLoadLibraryW(LPCWSTR);
static BOOL WINAPI traceBassInit(int,DWORD,DWORD,HWND,const GUID*);
static void patch_bass_loader_imports(HMODULE,unsigned);
static void patch_bass_cached_loader_pointers(HMODULE);

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

static BOOL CALLBACK initialize_trace_state(PINIT_ONCE unused,PVOID arg,PVOID *context){
    (void)unused;(void)arg;(void)context;
    wchar_t mutexName[96];
    swprintf(mutexName,96,L"Local\\WinlatorGameTrace-%lu",(unsigned long)GetCurrentProcessId());
    lock=CreateMutexW(NULL,FALSE,mutexName);
    if(!lock)return FALSE;
    InitializeCriticalSection(&dsMapLock);
    instance=GetTickCount();
    swprintf(tracePath,MAX_PATH,L"C:\\winlator-nvda\\config\\game-voice-%lu.jsonl",(unsigned long)GetCurrentProcessId());
    return TRUE;
}
static BOOL ensure_trace_state(void){
    return InitOnceExecuteOnce(&traceOnce,initialize_trace_state,NULL,NULL);
}
static BOOL audio_target_process(void){
    wchar_t path[MAX_PATH],*tail;
    DWORD count=GetModuleFileNameW(NULL,path,MAX_PATH);
    if(!count || count>=MAX_PATH)return FALSE;
    tail=wcsrchr(path,L'\\');tail=tail?tail+1:path;
    return !_wcsicmp(tail,L"zetianji.exe") || !_wcsicmp(tail,L"voice-trace-test.exe");
}
static void record_audio_preload(const char *state){
    DWORD saved=GetLastError();
    if(!ensure_trace_state()){SetLastError(saved);return;}
    DWORD acquired=WaitForSingleObject(lock,10);
    if(acquired!=WAIT_OBJECT_0 && acquired!=WAIT_ABANDONED_0){SetLastError(saved);return;}
    FILETIME utc;GetSystemTimeAsFileTime(&utc);
    unsigned long long epoch=((((unsigned long long)utc.dwHighDateTime<<32)|utc.dwLowDateTime)-116444736000000000ull)/10000ull;
    char line[512];
    int n=snprintf(line,sizeof(line),
        "{\"event\":\"audio-preload\",\"pid\":%lu,\"tid\":%lu,\"instance\":%lu,\"seq\":%ld,"
        "\"state\":\"%s\",\"tick\":%lu,\"timeMs\":%llu}\n",
        (unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId(),(unsigned long)instance,
        (long)InterlockedIncrement(&sequence),state,(unsigned long)GetTickCount(),epoch);
    if(n>0 && (size_t)n<sizeof(line))write_audio_line_locked(line,n);
    ReleaseMutex(lock);SetLastError(saved);
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
static int ascii_prefix_ci(const char *value,const char *prefix){
    if(!value || !prefix)return 0;
    for(size_t i=0;prefix[i];i++){
        char a=value[i],b=prefix[i];if(!a)return 0;
        if(a>='A'&&a<='Z')a=(char)(a-'A'+'a');
        if(b>='A'&&b<='Z')b=(char)(b-'A'+'a');
        if(a!=b)return 0;
    }
    return 1;
}
static int audio_module_name(const char *name){
    return name && (strstr(name,"bass")||strstr(name,"BASS")||strstr(name,"dsound")||strstr(name,"DSOUND")
        ||strstr(name,"winmm")||strstr(name,"WINMM")||strstr(name,"mmdevapi")||strstr(name,"MMDEVAPI")
        ||strstr(name,"openal")||strstr(name,"OpenAL")||strstr(name,"xaudio")||strstr(name,"XAudio"));
}
static void module_basename(HMODULE module,char *out,size_t cap){
    if(!out||!cap)return;
    out[0]=0;
    char path[MAX_PATH];DWORD n=module?GetModuleFileNameA(module,path,MAX_PATH):0;
    if(!n||n>=MAX_PATH)return;
    const char *tail=strrchr(path,'\\');tail=tail?tail+1:path;
    snprintf(out,cap,"%s",tail);
}
static void bounded_api_name(LPCSTR name,char *out,size_t cap){
    if(!out||!cap)return;
    out[0]=0;
    if((uintptr_t)name<=0xffffu){snprintf(out,cap,"#%u",(unsigned)(uintptr_t)name);return;}
    if(!readable_range(name,1))return;
    size_t i=0;for(;i+1<cap && i<96;i++){char ch=name[i];if(!ch)break;if(ch<32||ch>126)return;out[i]=ch;}
    out[i]=0;
}
static void record_audio_dynamic(const char *source,const char *action,HMODULE module,LPCSTR api,BOOL ok){
    char mod[96],name[128];module_basename(module,mod,sizeof(mod));bounded_api_name(api,name,sizeof(name));
    if(!audio_module_name(mod) && !ascii_prefix_ci(name,"BASS_") && !ascii_prefix_ci(name,"DirectSound"))return;
    if(InterlockedIncrement(&dynamicLogCount)>160)return;
    DWORD saved=GetLastError();if(!ensure_trace_state()){SetLastError(saved);return;}
    DWORD acquired=WaitForSingleObject(lock,10);
    if(acquired!=WAIT_OBJECT_0 && acquired!=WAIT_ABANDONED_0){SetLastError(saved);return;}
    FILETIME utc;GetSystemTimeAsFileTime(&utc);
    unsigned long long epoch=((((unsigned long long)utc.dwHighDateTime<<32)|utc.dwLowDateTime)-116444736000000000ull)/10000ull;
    char line[768];
    int n=snprintf(line,sizeof(line),
        "{\"event\":\"audio-dynamic\",\"pid\":%lu,\"tid\":%lu,\"instance\":%lu,\"seq\":%ld,"
        "\"source\":\"%s\",\"action\":\"%s\",\"module\":\"%s\",\"api\":\"%s\",\"ok\":%s,"
        "\"tick\":%lu,\"timeMs\":%llu}\n",
        (unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId(),(unsigned long)instance,
        (long)InterlockedIncrement(&sequence),source,action,mod,name,ok?"true":"false",
        (unsigned long)GetTickCount(),epoch);
    if(n>0&&(size_t)n<sizeof(line))write_audio_line_locked(line,n);
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

static uintptr_t canonical_code_pointer(uintptr_t value){
    for(unsigned step=0;value && step<8;step++){
        if(!readable_range((const void*)value,6))break;
        const unsigned char *code=(const unsigned char*)value;
        if(code[0]==0x90){value+=1;continue;}
        if(code[0]==0x8b && code[1]==0xff){value+=2;continue;}
        if(code[0]==0xe9){
            int32_t rel=0;memcpy(&rel,code+1,sizeof(rel));
            value=value+5+(intptr_t)rel;continue;
        }
        if(code[0]==0xeb){
            int8_t rel=(int8_t)code[1];value=value+2+(intptr_t)rel;continue;
        }
        if(code[0]==0xff && code[1]==0x25){
            uint32_t slot=0,target=0;memcpy(&slot,code+2,sizeof(slot));
            if(!slot || !readable_range((const void*)(uintptr_t)slot,sizeof(target)))break;
            memcpy(&target,(const void*)(uintptr_t)slot,sizeof(target));
            if(!target)break;
            value=(uintptr_t)target;continue;
        }
        break;
    }
    return value;
}
static BOOL equivalent_code_pointer(uintptr_t left,uintptr_t right){
    return left==right || (left && right && canonical_code_pointer(left)==canonical_code_pointer(right));
}
static HOOK_RESULT patch_import_address(HMODULE module,const char *wantedDll,FARPROC target,FARPROC replacement){
    HOOK_RESULT out={0};out.moduleFound=module!=NULL;out.originalReady=target!=NULL;
    if(!module || !wantedDll || !target || !replacement)return out;
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
        out.importDllFound=TRUE;out.nameTableFound=entry->OriginalFirstThunk!=0;
        if(!entry->FirstThunk || entry->FirstThunk>=image)continue;
        for(unsigned i=0;i<4096;i++){
            DWORD iatThunkRva=entry->FirstThunk+i*(DWORD)sizeof(IMAGE_THUNK_DATA32);
            if(iatThunkRva>image-sizeof(IMAGE_THUNK_DATA32))break;
            IMAGE_THUNK_DATA32 *iat=(IMAGE_THUNK_DATA32*)(base+iatThunkRva);
            DWORD current=iat->u1.Function;if(!current)break;
            DWORD replacement32=(DWORD)(uintptr_t)replacement;
            if(current==replacement32){out.importNameFound=TRUE;out.slots++;out.alreadyPatched++;continue;}
            if(!equivalent_code_pointer((uintptr_t)current,(uintptr_t)target))continue;
            out.importNameFound=TRUE;out.slots++;
            DWORD oldProtect=0;
            if(!VirtualProtect(&iat->u1.Function,sizeof(iat->u1.Function),PAGE_READWRITE,&oldProtect)){
                out.writeFailures++;continue;
            }
            iat->u1.Function=replacement32;
            DWORD unusedProtect=0;
            if(!VirtualProtect(&iat->u1.Function,sizeof(iat->u1.Function),oldProtect,&unusedProtect))
                out.writeFailures++;
            else out.patches++;
        }
    }
    return out;
}
static void patch_one_address(HOOK_STATE *state,HMODULE module,const char *source,const char *importDll,const char *api,
                              FARPROC target,FARPROC replacement,unsigned attempt){
    if(state->done)return;
    HOOK_RESULT result=patch_import_address(module,importDll,target,replacement);
    BOOL changed=!state->seen || !hook_result_equal(&state->last,&result);
    if(changed)record_audio_hook(source,importDll,api,attempt,&result);
    state->seen=TRUE;state->last=result;
    if(result.importNameFound && (result.patches||result.alreadyPatched) && result.writeFailures==0)state->done=TRUE;
}

static BOOL patch_vtable_slot(void **slot,void *replacement,void **original){
    if(!slot || !replacement || !readable_range(slot,sizeof(void*)))return FALSE;
    void *current=*slot;
    if(current==replacement)return TRUE;
    DWORD oldProtect=0;
    if(!VirtualProtect(slot,sizeof(void*),PAGE_EXECUTE_READWRITE,&oldProtect))return FALSE;
    *original=current;
    *slot=replacement;
    FlushInstructionCache(GetCurrentProcess(),slot,sizeof(void*));
    DWORD unused=0;VirtualProtect(slot,sizeof(void*),oldProtect,&unused);
    return TRUE;
}
static DSCreateBufferFn ds_create_buffer_original(void *object){
    if(!object || !readable_range(object,sizeof(void*)))return NULL;
    void **vtable=*(void***)object;DSCreateBufferFn result=NULL;
    EnterCriticalSection(&dsMapLock);
    for(unsigned i=0;i<dsVtableCount;i++)if(dsVtables[i].vtable==vtable){result=dsVtables[i].createBuffer;break;}
    LeaveCriticalSection(&dsMapLock);return result;
}
static void remember_ds_object(void *object){
    if(!object || !readable_range(object,sizeof(void*)))return;
    void **vtable=*(void***)object;if(!vtable || !readable_range(vtable,4*sizeof(void*)))return;
    EnterCriticalSection(&dsMapLock);
    for(unsigned i=0;i<dsVtableCount;i++)if(dsVtables[i].vtable==vtable){LeaveCriticalSection(&dsMapLock);return;}
    if(dsVtableCount<sizeof(dsVtables)/sizeof(dsVtables[0])){
        DS_VTABLE_ENTRY *row=&dsVtables[dsVtableCount];
        row->vtable=vtable;void *original=NULL;
        if(patch_vtable_slot(&vtable[3],(void*)(uintptr_t)traceDSCreateSoundBuffer,&original)){
            row->createBuffer=(DSCreateBufferFn)(uintptr_t)original;dsVtableCount++;
        }
    }
    LeaveCriticalSection(&dsMapLock);
}
static void remember_buffer_object_locked(void *object,int format,int rate){
    for(unsigned i=0;i<dsBufferObjectCount;i++)if(dsBufferObjects[i].object==object){
        dsBufferObjects[i].format=format;dsBufferObjects[i].rate=rate;return;
    }
    if(dsBufferObjectCount<sizeof(dsBufferObjects)/sizeof(dsBufferObjects[0])){
        dsBufferObjects[dsBufferObjectCount].object=object;
        dsBufferObjects[dsBufferObjectCount].format=format;
        dsBufferObjects[dsBufferObjectCount].rate=rate;dsBufferObjectCount++;
    }
}
static void remember_ds_buffer(void *object,int format,int rate){
    if(!object || !readable_range(object,sizeof(void*)))return;
    void **vtable=*(void***)object;if(!vtable || !readable_range(vtable,20*sizeof(void*)))return;
    EnterCriticalSection(&dsMapLock);
    remember_buffer_object_locked(object,format,rate);
    for(unsigned i=0;i<dsBufferVtableCount;i++)if(dsBufferVtables[i].vtable==vtable){
        LeaveCriticalSection(&dsMapLock);return;
    }
    if(dsBufferVtableCount<sizeof(dsBufferVtables)/sizeof(dsBufferVtables[0])){
        DS_BUFFER_VTABLE_ENTRY *row=&dsBufferVtables[dsBufferVtableCount];
        row->vtable=vtable;void *unlockOriginal=NULL,*playOriginal=NULL;
        BOOL unlockOk=patch_vtable_slot(&vtable[19],(void*)(uintptr_t)traceDSBufferUnlock,&unlockOriginal);
        BOOL playOk=patch_vtable_slot(&vtable[12],(void*)(uintptr_t)traceDSBufferPlay,&playOriginal);
        if(unlockOk && playOk){
            row->unlock=(DSBufferUnlockFn)(uintptr_t)unlockOriginal;
            row->play=(DSBufferPlayFn)(uintptr_t)playOriginal;dsBufferVtableCount++;
        }
    }
    LeaveCriticalSection(&dsMapLock);
}
static void ds_buffer_functions(void *object,DSBufferUnlockFn *unlock,DSBufferPlayFn *play,int *format,int *rate){
    *unlock=NULL;*play=NULL;*format=0;*rate=0;
    if(!object || !readable_range(object,sizeof(void*)))return;
    void **vtable=*(void***)object;
    EnterCriticalSection(&dsMapLock);
    for(unsigned i=0;i<dsBufferVtableCount;i++)if(dsBufferVtables[i].vtable==vtable){
        *unlock=dsBufferVtables[i].unlock;*play=dsBufferVtables[i].play;break;
    }
    for(unsigned i=0;i<dsBufferObjectCount;i++)if(dsBufferObjects[i].object==object){
        *format=dsBufferObjects[i].format;*rate=dsBufferObjects[i].rate;break;
    }
    LeaveCriticalSection(&dsMapLock);
}
static HRESULT WINAPI traceDSCreateSoundBuffer(void *object,const DSBUFFERDESC_MIN *desc,void **buffer,IUnknown *outer){
    DWORD saved=GetLastError();DSCreateBufferFn originalFn=ds_create_buffer_original(object);
    DSBUFFERDESC_MIN copy={0};int format=0,rate=0;SIZE_T bytes=0;
    if(desc && readable_range(desc,sizeof(copy))){
        memcpy(&copy,desc,sizeof(copy));bytes=copy.dwBufferBytes;
        WAVEFORMATEX wave;
        if(copy.lpwfxFormat && readable_range(copy.lpwfxFormat,sizeof(wave))){
            memcpy(&wave,copy.lpwfxFormat,sizeof(wave));format=wave.wFormatTag;rate=(int)wave.nSamplesPerSec;
        }
    }
    SetLastError(saved);HRESULT result=originalFn?originalFn(object,desc,buffer,outer):E_FAIL;DWORD error=GetLastError();
    if(SUCCEEDED(result)&&buffer&&readable_range(buffer,sizeof(void*))&&*buffer)remember_ds_buffer(*buffer,format,rate);
    record_audio(&directSoundBufferCreateStat,"DirectSound::CreateSoundBuffer","bass.dll",bytes,0,0,format,rate,(int)result);
    SetLastError(error);return result;
}
static HRESULT WINAPI traceDSBufferUnlock(void *object,void *first,DWORD firstBytes,void *second,DWORD secondBytes){
    DWORD saved=GetLastError();DSBufferUnlockFn unlock=NULL;DSBufferPlayFn play=NULL;int format=0,rate=0;
    ds_buffer_functions(object,&unlock,&play,&format,&rate);(void)play;
    SIZE_T sampled1=0,sampled2=0,nonzero=0;
    if(first&&firstBytes)nonzero+=sample_nonzero(first,firstBytes,&sampled1);
    if(second&&secondBytes)nonzero+=sample_nonzero(second,secondBytes,&sampled2);
    SetLastError(saved);HRESULT result=unlock?unlock(object,first,firstBytes,second,secondBytes):E_FAIL;DWORD error=GetLastError();
    record_audio(&directSoundBufferUnlockStat,"DirectSoundBuffer::Unlock","bass.dll",
                 (SIZE_T)firstBytes+(SIZE_T)secondBytes,sampled1+sampled2,nonzero,format,rate,(int)result);
    SetLastError(error);return result;
}
static HRESULT WINAPI traceDSBufferPlay(void *object,DWORD reserved1,DWORD priority,DWORD flags){
    DWORD saved=GetLastError();DSBufferUnlockFn unlock=NULL;DSBufferPlayFn play=NULL;int format=0,rate=0;
    ds_buffer_functions(object,&unlock,&play,&format,&rate);(void)unlock;
    SetLastError(saved);HRESULT result=play?play(object,reserved1,priority,flags):E_FAIL;DWORD error=GetLastError();
    record_audio(&directSoundBufferPlayStat,"DirectSoundBuffer::Play","bass.dll",0,0,0,format,rate,(int)result);
    SetLastError(error);return result;
}
static HRESULT WINAPI traceDirectSoundCreate(const GUID *guid,void **out,IUnknown *outer){
    DWORD saved=GetLastError();SetLastError(saved);
    HRESULT result=realDirectSoundCreate?realDirectSoundCreate(guid,out,outer):E_FAIL;DWORD error=GetLastError();
    if(SUCCEEDED(result)&&out&&readable_range(out,sizeof(void*))&&*out)remember_ds_object(*out);
    record_audio(&directSoundCreateStat,"DirectSoundCreate","bass.dll",0,0,0,0,0,(int)result);
    SetLastError(error);return result;
}
static HRESULT WINAPI traceDirectSoundCreate8(const GUID *guid,void **out,IUnknown *outer){
    DWORD saved=GetLastError();SetLastError(saved);
    HRESULT result=realDirectSoundCreate8?realDirectSoundCreate8(guid,out,outer):E_FAIL;DWORD error=GetLastError();
    if(SUCCEEDED(result)&&out&&readable_range(out,sizeof(void*))&&*out)remember_ds_object(*out);
    record_audio(&directSoundCreateStat,"DirectSoundCreate8","bass.dll",0,0,0,0,0,(int)result);
    SetLastError(error);return result;
}
static int module_is(HMODULE module,const char *wanted){
    char name[96];module_basename(module,name,sizeof(name));return name[0]&&!_stricmp(name,wanted);
}
static FARPROC WINAPI traceBassGetProcAddress(HMODULE module,LPCSTR name){
    FARPROC result=realKernelGetProcAddress?realKernelGetProcAddress(module,name):NULL;
    char api[128];bounded_api_name(name,api,sizeof(api));record_audio_dynamic("bass.dll","GetProcAddress",module,name,result!=NULL);
    if(result && module_is(module,"dsound.dll")){
        if(!strcmp(api,"DirectSoundCreate8")){
            realDirectSoundCreate8=(DirectSoundCreateFn)(uintptr_t)result;
            return (FARPROC)(uintptr_t)traceDirectSoundCreate8;
        }
        if(!strcmp(api,"DirectSoundCreate")){
            realDirectSoundCreate=(DirectSoundCreateFn)(uintptr_t)result;
            return (FARPROC)(uintptr_t)traceDirectSoundCreate;
        }
    }
    return result;
}
static HMODULE WINAPI traceBassLoadLibraryA(LPCSTR name){
    HMODULE result=realKernelLoadLibraryA?realKernelLoadLibraryA(name):NULL;
    record_audio_dynamic("bass.dll","LoadLibraryA",result,"LoadLibraryA",result!=NULL);return result;
}
static HMODULE WINAPI traceBassLoadLibraryW(LPCWSTR name){
    HMODULE result=realKernelLoadLibraryW?realKernelLoadLibraryW(name):NULL;
    record_audio_dynamic("bass.dll","LoadLibraryW",result,"LoadLibraryW",result!=NULL);return result;
}
static HOOK_STATE bassGetProcState,bassLoadAState,bassLoadWState;
static void patch_bass_loader_imports(HMODULE bass,unsigned attempt){
    if(!bass)return;
    patch_one_address(&bassGetProcState,bass,"bass.dll","KERNEL32.dll","GetProcAddress(address)",
                      (FARPROC)(uintptr_t)realKernelGetProcAddress,(FARPROC)(uintptr_t)traceBassGetProcAddress,attempt);
    patch_one_address(&bassLoadAState,bass,"bass.dll","KERNEL32.dll","LoadLibraryA(address)",
                      (FARPROC)(uintptr_t)realKernelLoadLibraryA,(FARPROC)(uintptr_t)traceBassLoadLibraryA,attempt);
    patch_one_address(&bassLoadWState,bass,"bass.dll","KERNEL32.dll","LoadLibraryW(address)",
                      (FARPROC)(uintptr_t)realKernelLoadLibraryW,(FARPROC)(uintptr_t)traceBassLoadLibraryW,attempt);
}
static FARPROC WINAPI traceGameGetProcAddress(HMODULE module,LPCSTR name){
    FARPROC result=realKernelGetProcAddress?realKernelGetProcAddress(module,name):NULL;
    record_audio_dynamic("zetianji.exe","GetProcAddress",module,name,result!=NULL);return result;
}
static HMODULE WINAPI traceGameLoadLibraryA(LPCSTR name){
    HMODULE result=realKernelLoadLibraryA?realKernelLoadLibraryA(name):NULL;
    record_audio_dynamic("zetianji.exe","LoadLibraryA",result,"LoadLibraryA",result!=NULL);
    if(result && module_is(result,"bass.dll"))patch_bass_loader_imports(result,0);
    return result;
}
static HMODULE WINAPI traceGameLoadLibraryW(LPCWSTR name){
    HMODULE result=realKernelLoadLibraryW?realKernelLoadLibraryW(name):NULL;
    record_audio_dynamic("zetianji.exe","LoadLibraryW",result,"LoadLibraryW",result!=NULL);
    if(result && module_is(result,"bass.dll"))patch_bass_loader_imports(result,0);
    return result;
}

static DWORD WINAPI audio_hook_thread(void *unused){
    (void)unused;
    if(!audio_target_process())return 0;
    wchar_t ownerName[96];
    swprintf(ownerName,96,L"Local\\WinlatorAudioProbe-%lu",(unsigned long)GetCurrentProcessId());
    HANDLE owner=CreateMutexW(NULL,FALSE,ownerName);
    DWORD ownerError=GetLastError();
    if(!owner)return 0;
    if(ownerError==ERROR_ALREADY_EXISTS){CloseHandle(owner);return 0;}
    if(!ensure_trace_state()){CloseHandle(owner);return 0;}
    HMODULE pin=NULL;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,(LPCWSTR)(ULONG_PTR)&audio_hook_thread,&pin);
    record_audio_preload("started");
    HOOK_STATE gameGetProc={0},gameLoadA={0},gameLoadW={0};
    HOOK_STATE zetWave={0},openalWave={0},bassWave={0},aiWave={0},soundBuffer={0},soundPlay={0};
    for(unsigned attempt=0;attempt<1700;attempt++){
        HMODULE kernel32=GetModuleHandleW(L"kernel32.dll");
        if(kernel32 && !realKernelGetProcAddress)
            realKernelGetProcAddress=(GetProcAddressFn)(ULONG_PTR)GetProcAddress(kernel32,"GetProcAddress");
        if(kernel32 && !realKernelLoadLibraryA)
            realKernelLoadLibraryA=(LoadLibraryAFn)(ULONG_PTR)GetProcAddress(kernel32,"LoadLibraryA");
        if(kernel32 && !realKernelLoadLibraryW)
            realKernelLoadLibraryW=(LoadLibraryWFn)(ULONG_PTR)GetProcAddress(kernel32,"LoadLibraryW");
        HMODULE mainModule=GetModuleHandleW(NULL);
        patch_one_name(&gameGetProc,mainModule,"zetianji.exe","KERNEL32.dll","GetProcAddress",
                       (FARPROC)(ULONG_PTR)traceGameGetProcAddress,realKernelGetProcAddress!=NULL,attempt);
        patch_one_name(&gameLoadA,mainModule,"zetianji.exe","KERNEL32.dll","LoadLibraryA",
                       (FARPROC)(ULONG_PTR)traceGameLoadLibraryA,realKernelLoadLibraryA!=NULL,attempt);
        patch_one_name(&gameLoadW,mainModule,"zetianji.exe","KERNEL32.dll","LoadLibraryW",
                       (FARPROC)(ULONG_PTR)traceGameLoadLibraryW,realKernelLoadLibraryW!=NULL,attempt);
        patch_bass_loader_imports(GetModuleHandleW(L"bass.dll"),attempt);
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
        Sleep(attempt<1200?10:100);
    }
    record_audio_preload("finished");
    CloseHandle(owner);
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
    if(!ensure_trace_state())return FALSE;
    record("proxy.loadOriginal","begin",0,0,0,0,NULL,0);
    DWORD began=GetTickCount();SetLastError(0);original=LoadLibraryW(path);DWORD error=original?0:GetLastError();
    record("proxy.loadOriginal","end",0,original!=NULL,error,GetTickCount()-began,NULL,0);
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
    (void)unused;
    if(reason==DLL_PROCESS_ATTACH){
        self=module;DisableThreadLibraryCalls(module);
        HANDLE thread=CreateThread(NULL,0,audio_hook_thread,NULL,0,NULL);
        if(thread)CloseHandle(thread);
    }
    return TRUE;
}
