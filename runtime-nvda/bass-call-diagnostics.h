/* SPDX-License-Identifier: MIT. Included by voice-trace.c; never reads PCM or logs pointers. */
#define BASS_PATH_CHARS 384
static BOOL ensure_trace_state(void);
static BOOL bass_can_request_dsound(DWORD version){
    return (version>>16)==0x0204u && version>=0x02040d00u;
}
static DWORD bass_diagnostic_version(void){
    HMODULE bass=GetModuleHandleW(L"bass.dll");
    if(bass && realKernelGetProcAddress){
        if(!realBassGetVersion)realBassGetVersion=(BassGetVersionFn)(uintptr_t)realKernelGetProcAddress(bass,"BASS_GetVersion");
        if(!realBassErrorGetCode)realBassErrorGetCode=(BassErrorGetCodeFn)(uintptr_t)realKernelGetProcAddress(bass,"BASS_ErrorGetCode");
    }
    return realBassGetVersion?realBassGetVersion():0;
}
typedef struct {
    BOOL memory,pathReady,pathLimited,cwdReady,exists,readable,sizeAvailable;
    DWORD probeError;
    unsigned long long fileBytes;
    wchar_t path[BASS_PATH_CHARS],cwd[BASS_PATH_CHARS];
    const char *state;
} BASS_FILE_INPUT;
/* Emit ASCII JSON, including surrogate escapes, so the existing ASCII trace reader
   preserves Chinese paths exactly. Never interpolate a filename into JSON raw. */
static void bass_json_path(const wchar_t *path,char *out,SIZE_T capacity){
    SIZE_T n=0;
    for(SIZE_T i=0;path[i] && n+7<capacity;i++){
        unsigned c=(unsigned short)path[i];
        if(c>=32 && c<127 && c!='"' && c!='\\')out[n++]=(char)c;
        else {int count=snprintf(out+n,capacity-n,"\\u%04x",c);if(count!=6)break;n+=6;}
    }
    out[n]=0;
}
static void describe_bass_input(BASS_FILE_INPUT *out,BOOL memory,const void *file,DWORD flags){
    memset(out,0,sizeof(*out));out->memory=memory;out->state=memory?"memory-not-inspected":"null-path";
    if(memory)return;
    DWORD cwd=GetCurrentDirectoryW(BASS_PATH_CHARS,out->cwd);
    out->cwdReady=cwd>0 && cwd<BASS_PATH_CHARS;
    if(!out->cwdReady)out->cwd[0]=0;
    if(!file)return;
    wchar_t raw[BASS_PATH_CHARS];SIZE_T i;
    if(flags&0x80000000u){
        const wchar_t *wide=(const wchar_t*)file;
        for(i=0;i<BASS_PATH_CHARS-1;i++){
            if(!readable_range(wide+i,sizeof(*wide))){out->state="unreadable-path";return;}
            raw[i]=wide[i];if(!raw[i])break;
        }
    }else{
        const char *ansi=(const char*)file;char text[BASS_PATH_CHARS];
        for(i=0;i<BASS_PATH_CHARS-1;i++){
            if(!readable_range(ansi+i,1)){out->state="unreadable-path";return;}
            text[i]=ansi[i];if(!text[i])break;
        }
        if(i==BASS_PATH_CHARS-1){out->pathLimited=TRUE;out->state="path-too-long";return;}
        if(!MultiByteToWideChar(CP_ACP,0,text,-1,raw,BASS_PATH_CHARS)){
            out->probeError=GetLastError();out->state="path-conversion-failed";return;
        }
    }
    if(i==BASS_PATH_CHARS-1){out->pathLimited=TRUE;out->state="path-too-long";return;}
    DWORD count=GetFullPathNameW(raw,BASS_PATH_CHARS,out->path,NULL);
    if(!count || count>=BASS_PATH_CHARS){
        out->path[0]=0;out->pathLimited=count>=BASS_PATH_CHARS;
        out->probeError=count?ERROR_BUFFER_OVERFLOW:GetLastError();out->state="path-resolution-failed";return;
    }
    out->pathReady=TRUE;out->state="resolved";
}
static void probe_bass_file(BASS_FILE_INPUT *out){
    if(!out->pathReady)return;
    DWORD attributes=GetFileAttributesW(out->path);
    if(attributes==INVALID_FILE_ATTRIBUTES){out->probeError=GetLastError();out->state="attributes-failed";return;}
    out->exists=TRUE;
    if(attributes&FILE_ATTRIBUTE_DIRECTORY){out->state="directory";return;}
    HANDLE file=CreateFileW(out->path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                            NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE){out->probeError=GetLastError();out->state="open-failed";return;}
    out->readable=TRUE;LARGE_INTEGER bytes;
    if(GetFileSizeEx(file,&bytes)){out->fileBytes=(unsigned long long)bytes.QuadPart;out->sizeAvailable=TRUE;}
    else out->probeError=GetLastError();
    CloseHandle(file);out->state="readable";
}
static LONG bassInitCallLogs,bassStreamCallLogs,bassPlayCallLogs;
static void record_bass_call(const char *api,BOOL result,int bassError,DWORD version,DWORD flags,
                             uint64_t offset,uint64_t length,const BASS_FILE_INPUT *input,int device,int restart){
    LONG *counter=!strcmp(api,"BASS_Init")?&bassInitCallLogs:
                  (!strcmp(api,"BASS_StreamCreateFile")?&bassStreamCallLogs:&bassPlayCallLogs);
    LONG call=InterlockedIncrement(counter);
    /* Bounded per API; Play traffic cannot consume stream diagnostics. */
    if(call>128)return;
    DWORD saved=GetLastError();if(!ensure_trace_state()){SetLastError(saved);return;}
    char path[BASS_PATH_CHARS*6+1]={0},cwd[BASS_PATH_CHARS*6+1]={0};
    if(input){bass_json_path(input->path,path,sizeof(path));bass_json_path(input->cwd,cwd,sizeof(cwd));}
    DWORD acquired=WaitForSingleObject(lock,10);
    if(acquired!=WAIT_OBJECT_0 && acquired!=WAIT_ABANDONED_0){SetLastError(saved);return;}
    FILETIME utc;GetSystemTimeAsFileTime(&utc);
    unsigned long long epoch=((((unsigned long long)utc.dwHighDateTime<<32)|utc.dwLowDateTime)-116444736000000000ull)/10000ull;
    char line[8192];
    int n=snprintf(line,sizeof(line),
        "{\"event\":\"audio-bass-call\",\"pid\":%lu,\"tid\":%lu,\"instance\":%lu,\"seq\":%ld,"
        "\"source\":\"bass.dll\",\"api\":\"%s\",\"call\":%ld,\"result\":%s,\"bassError\":%d,"
        "\"bassErrorAvailable\":%s,\"bassVersion\":%lu,\"flags\":%lu,\"offset\":%llu,\"length\":%llu,"
        "\"device\":%d,\"restart\":%s,\"sourceKind\":\"%s\",\"fileState\":\"%s\","
        "\"path\":\"%s\",\"cwd\":\"%s\",\"pathLimited\":%s,\"cwdReady\":%s,\"fileExists\":%s,"
        "\"fileReadable\":%s,\"fileSizeAvailable\":%s,\"fileBytes\":%llu,\"fileProbeError\":%lu,"
        "\"timeMs\":%llu}\n",
        (unsigned long)GetCurrentProcessId(),(unsigned long)GetCurrentThreadId(),(unsigned long)instance,
        (long)InterlockedIncrement(&sequence),api,(long)call,result?"true":"false",bassError,
        realBassErrorGetCode?"true":"false",(unsigned long)version,(unsigned long)flags,
        (unsigned long long)offset,(unsigned long long)length,device,restart?"true":"false",
        !input?"none":input->memory?"memory":"file",input?input->state:"not-applicable",path,cwd,
        input&&input->pathLimited?"true":"false",input&&input->cwdReady?"true":"false",
        input&&input->exists?"true":"false",input&&input->readable?"true":"false",
        input&&input->sizeAvailable?"true":"false",input?input->fileBytes:0,
        (unsigned long)(input?input->probeError:0),epoch);
    if(n>0&&(size_t)n<sizeof(line))write_audio_line_locked(line,n);
    ReleaseMutex(lock);SetLastError(saved);
}
