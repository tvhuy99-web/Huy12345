/* SPDX-License-Identifier: MIT. Bounded PE32 observer and optional debugger snapshot. */
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
static BOOL unresponsive;
static DWORD tids[32];
static unsigned threadCount;
static MODULEENTRY32W moduleList[96];
static unsigned moduleCount;
typedef struct {BOOL tried;DWORD count,names,base,size;DWORD *functions,*strings;WORD *ordinals;} SYMBOLS;
static SYMBOLS symbols[96];
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
/* Only numeric registers/code addresses leave the process. Stack words are never emitted. */
typedef struct {
    DWORD tid,error,eip,esp,ebp,frames[8],candidates[16];
    unsigned frameCount,candidateCount;
    BOOL opened,contextOk;
} THREAD_SAMPLE;
static BOOL read_memory(HANDLE process,DWORD address,void *buffer,SIZE_T size){
    SIZE_T copied=0;
    return ReadProcessMemory(process,(void*)(ULONG_PTR)address,buffer,size,&copied)&&copied==size;
}
static int module_index(DWORD value){
    for(unsigned i=0;i<moduleCount;i++){
        DWORD base=(DWORD)(ULONG_PTR)moduleList[i].modBaseAddr;
        if(value>=base && value-base<moduleList[i].modBaseSize)return (int)i;
    }
    return -1;
}
static BOOL code_address(HANDLE process,DWORD value){
    MEMORY_BASIC_INFORMATION region={0};
    return module_index(value)>=0 && VirtualQueryEx(process,(void*)(ULONG_PTR)value,&region,sizeof(region))
        && region.State==MEM_COMMIT && !(region.Protect&(PAGE_GUARD|PAGE_NOACCESS))
        && (region.Protect&(PAGE_EXECUTE|PAGE_EXECUTE_READ|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY));
}
static BOOL image_read(HANDLE process,unsigned index,DWORD rva,void *buffer,SIZE_T size){
    DWORD bytes=moduleList[index].modBaseSize,base=(DWORD)(ULONG_PTR)moduleList[index].modBaseAddr;
    return rva<bytes && size<=bytes-rva && read_memory(process,base+rva,buffer,size);
}
static void export_hint(HANDLE process,unsigned index,DWORD rva){
    SYMBOLS *table=&symbols[index];
    if(!table->tried){
        table->tried=TRUE;
        IMAGE_DOS_HEADER dos;IMAGE_NT_HEADERS32 nt;IMAGE_EXPORT_DIRECTORY exports;
        if(!image_read(process,index,0,&dos,sizeof(dos)) || dos.e_magic!=IMAGE_DOS_SIGNATURE || dos.e_lfanew<0
           || !image_read(process,index,(DWORD)dos.e_lfanew,&nt,sizeof(nt)) || nt.Signature!=IMAGE_NT_SIGNATURE
           || nt.OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC || nt.OptionalHeader.NumberOfRvaAndSizes<=IMAGE_DIRECTORY_ENTRY_EXPORT)return;
        IMAGE_DATA_DIRECTORY directory=nt.OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT];
        if(!directory.VirtualAddress || !image_read(process,index,directory.VirtualAddress,&exports,sizeof(exports))
           || !exports.NumberOfFunctions || !exports.NumberOfNames || exports.NumberOfFunctions>8192 || exports.NumberOfNames>8192)return;
        DWORD *functions=calloc(exports.NumberOfFunctions,sizeof(DWORD)),*strings=calloc(exports.NumberOfNames,sizeof(DWORD));
        WORD *ordinals=calloc(exports.NumberOfNames,sizeof(WORD));
        if(!functions || !strings || !ordinals
           || !image_read(process,index,exports.AddressOfFunctions,functions,exports.NumberOfFunctions*sizeof(DWORD))
           || !image_read(process,index,exports.AddressOfNames,strings,exports.NumberOfNames*sizeof(DWORD))
           || !image_read(process,index,exports.AddressOfNameOrdinals,ordinals,exports.NumberOfNames*sizeof(WORD))){
            free(functions);free(strings);free(ordinals);return;
        }
        table->functions=functions;table->strings=strings;table->ordinals=ordinals;
        table->count=exports.NumberOfFunctions;table->names=exports.NumberOfNames;table->base=directory.VirtualAddress;table->size=directory.Size;
    }
    DWORD best=0,bestName=0;
    for(DWORD i=0;i<table->names;i++){
        if(table->ordinals[i]>=table->count)continue;
        DWORD function=table->functions[table->ordinals[i]];
        if(function>=table->base && function-table->base<table->size)continue; /* PE forwarder. */
        if(function && function<=rva && rva-function<=4096 && function>best){best=function;bestName=table->strings[i];}
    }
    if(best){
        char name[96]={0};SIZE_T copied=0;DWORD bytes=moduleList[index].modBaseSize;
        if(bestName>=bytes)return;
        SIZE_T length=bytes-bestName<sizeof(name)?bytes-bestName:sizeof(name);
        if(!ReadProcessMemory(process,(void*)(ULONG_PTR)((DWORD)(ULONG_PTR)moduleList[index].modBaseAddr+bestName),name,length,&copied))return;
        unsigned n=0;
        while(n<copied && name[n]){if(!strchr("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_@?$.",name[n]))return;n++;}
        if(!n || n==copied)return;
        /* This is a proximity hint, not a symbolized stack/unwind or a proven active API. */
        fprintf(out,",\"nearestExport\":\"%s\",\"exportDistance\":%lu",name,(unsigned long)(rva-best));
    }
}
static void address(HANDLE process,DWORD value){
    int index=module_index(value);
    fprintf(out,"{\"address\":%lu",(unsigned long)value);
    if(index>=0){fprintf(out,",\"module\":");string(moduleList[index].szModule);
        DWORD rva=value-(DWORD)(ULONG_PTR)moduleList[index].modBaseAddr;
        fprintf(out,",\"rva\":%lu",(unsigned long)rva);export_hint(process,(unsigned)index,rva);}
    fprintf(out,"}");
}
static void sample_threads(HANDLE process,THREAD_SAMPLE *samples,unsigned *count){
    for(unsigned i=0;i<threadCount && *count<12;i++){
        THREAD_SAMPLE *sample=&samples[(*count)++];sample->tid=tids[i];
        HANDLE thread=OpenThread(THREAD_GET_CONTEXT|THREAD_QUERY_INFORMATION,FALSE,sample->tid);
        sample->opened=thread!=NULL;
        if(!thread){sample->error=GetLastError();continue;}
        CONTEXT context={0};context.ContextFlags=CONTEXT_CONTROL;
        sample->contextOk=GetThreadContext(thread,&context);
        sample->error=sample->contextOk?0:GetLastError();CloseHandle(thread);
        if(!sample->contextOk)continue;
        sample->eip=context.Eip;sample->esp=context.Esp;sample->ebp=context.Ebp;
        DWORD frame=context.Ebp;
        for(unsigned j=0;j<8;j++){
            DWORD pair[2];
            if(frame<context.Esp || frame-context.Esp>1048576 || (frame&3)
               || !read_memory(process,frame,pair,sizeof(pair)) || !code_address(process,pair[1]))break;
            sample->frames[sample->frameCount++]=pair[1];
            if(pair[0]<=frame || pair[0]-frame>1048576)break;
            frame=pair[0];
        }
        DWORD words[128]={0};SIZE_T copied=0;
        /* Candidates are deliberately labelled: executable stack words are not a call stack. */
        if(ReadProcessMemory(process,(void*)(ULONG_PTR)context.Esp,words,sizeof(words),&copied)){
            for(unsigned j=0;j<copied/sizeof(DWORD)&&sample->candidateCount<16;j++){
                if(!code_address(process,words[j]))continue;
                BOOL duplicate=FALSE;
                for(unsigned k=0;k<sample->candidateCount;k++)if(sample->candidates[k]==words[j])duplicate=TRUE;
                if(!duplicate)sample->candidates[sample->candidateCount++]=words[j];
            }
        }
    }
}
/* Establish detach-on-exit using only an expendable child of this helper, before
   ever attaching to the user's game. The setting covers future debug connections. */
static BOOL detach_guard(DWORD *error){
    wchar_t executable[MAX_PATH],command[MAX_PATH*2];
    DWORD length=GetModuleFileNameW(NULL,executable,MAX_PATH);
    if(!length || length>=MAX_PATH){*error=ERROR_INSUFFICIENT_BUFFER;return FALSE;}
    swprintf(command,MAX_PATH*2,L"\"%ls\" --debug-guard",executable);
    STARTUPINFOW startup={0};startup.cb=sizeof(startup);PROCESS_INFORMATION child={0};
    if(!CreateProcessW(executable,command,NULL,NULL,FALSE,DEBUG_ONLY_THIS_PROCESS|CREATE_NO_WINDOW,NULL,NULL,&startup,&child)){
        *error=GetLastError();return FALSE;
    }
    BOOL guarded=DebugSetProcessKillOnExit(FALSE);if(!guarded)*error=GetLastError();
    BOOL detached=DebugActiveProcessStop(child.dwProcessId);if(!detached && guarded)*error=GetLastError();
    /* Only our own helper child, never the game. */
    TerminateProcess(child.hProcess,0);WaitForSingleObject(child.hProcess,200);
    CloseHandle(child.hThread);CloseHandle(child.hProcess);
    return guarded&&detached;
}
static void debug_snapshot(HANDLE process){
    DWORD began=GetTickCount(),attachError=0,guardError=0,waitError=0,continueError=0,detachError=0;
    BOOL attached=FALSE,guard=FALSE,detached=FALSE,captured=FALSE,breakpoint=FALSE,exited=FALSE;
    unsigned events=0,count=0;THREAD_SAMPLE samples[12]={0};
    BOOL already=FALSE;
    if(!CheckRemoteDebuggerPresent(process,&already)||already){
        fprintf(out,",\"threadSnapshot\":{\"attempted\":false,\"reason\":\"debugger-present-or-query-failed\"}");return;
    }
    guard=detach_guard(&guardError);
    if(guard){attached=DebugActiveProcess(target);if(!attached)attachError=GetLastError();}
    if(attached){
        if(guard){
            while(GetTickCount()-began<1800 && events<256){
                DEBUG_EVENT event={0};
                if(!WaitForDebugEvent(&event,50)){
                    DWORD error=GetLastError();if(error==ERROR_SEM_TIMEOUT)continue;
                    waitError=error;break;
                }
                events++;
                /* The OS has paused all target threads for this event; no SuspendThread is used.
                   Capture before continuing the initial attach event, before the synthetic break. */
                if(!captured && event.dwProcessId==target && event.dwDebugEventCode==CREATE_PROCESS_DEBUG_EVENT){
                    sample_threads(process,samples,&count);captured=TRUE;
#ifdef PROBE_TEST_ABORT
                    /* CI builds only: kill the helper while a debug event pauses the target. */
                    Sleep(30000);
#endif
                }
                DWORD disposition=DBG_CONTINUE;
                if(event.dwDebugEventCode==EXCEPTION_DEBUG_EVENT){
                    breakpoint=event.u.Exception.ExceptionRecord.ExceptionCode==EXCEPTION_BREAKPOINT;
                    disposition=breakpoint?DBG_CONTINUE:DBG_EXCEPTION_NOT_HANDLED;
                }
                if(event.dwDebugEventCode==CREATE_PROCESS_DEBUG_EVENT){
                    if(event.u.CreateProcessInfo.hFile)CloseHandle(event.u.CreateProcessInfo.hFile);
                }
                if(event.dwDebugEventCode==LOAD_DLL_DEBUG_EVENT && event.u.LoadDll.hFile)CloseHandle(event.u.LoadDll.hFile);
                exited=event.dwDebugEventCode==EXIT_PROCESS_DEBUG_EVENT;
                if(!ContinueDebugEvent(event.dwProcessId,event.dwThreadId,disposition)){continueError=GetLastError();break;}
                if(breakpoint||exited)break;
            }
        }
        detached=DebugActiveProcessStop(target);if(!detached)detachError=GetLastError();
    }
    fprintf(out,",\"threadSnapshot\":{\"attempted\":true,\"attached\":%s,\"attachError\":%lu,\"detachOnExit\":%s,\"guardError\":%lu,\"detached\":%s,\"detachError\":%lu,\"capturedBeforeAttachBreakpoint\":%s,\"sawAttachBreakpoint\":%s,\"targetExited\":%s,\"waitError\":%lu,\"continueError\":%lu,\"events\":%u,\"elapsedMs\":%lu,\"samples\":[",
        attached?"true":"false",(unsigned long)attachError,guard?"true":"false",(unsigned long)guardError,
        detached?"true":"false",(unsigned long)detachError,captured?"true":"false",breakpoint?"true":"false",exited?"true":"false",
        (unsigned long)waitError,(unsigned long)continueError,events,(unsigned long)(GetTickCount()-began));
    for(unsigned i=0;i<count;i++){
        THREAD_SAMPLE *sample=&samples[i];if(i)fputc(',',out);
        fprintf(out,"{\"tid\":%lu,\"opened\":%s,\"contextOk\":%s,\"error\":%lu",(unsigned long)sample->tid,sample->opened?"true":"false",sample->contextOk?"true":"false",(unsigned long)sample->error);
        if(sample->contextOk){
            fprintf(out,",\"instruction\":");address(process,sample->eip);
            fprintf(out,",\"framePointerChainUnverified\":[");
            for(unsigned j=0;j<sample->frameCount;j++){if(j)fputc(',',out);address(process,sample->frames[j]);}
            fprintf(out,"],\"stackCodeCandidatesNotCallStack\":[");
            for(unsigned j=0;j<sample->candidateCount;j++){if(j)fputc(',',out);address(process,sample->candidates[j]);}
            fputc(']',out);
        }
        fputc('}',out);
    }
    fprintf(out,"]}");
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
    if(!sent && !IsWindowVisible(hwnd))unresponsive=TRUE;
    fprintf(out,"{\"hwnd\":%lu,\"thread\":%lu,\"class\":",(unsigned long)(ULONG_PTR)hwnd,(unsigned long)tid);string(kind);
    fprintf(out,",\"visible\":%s,\"enabled\":%s,\"style\":%lu,\"exStyle\":%lu,\"rect\":[%ld,%ld,%ld,%ld],\"wmNullDelivered\":%s,\"pingError\":%lu,\"pingMs\":%lu}",
        IsWindowVisible(hwnd)?"true":"false",IsWindowEnabled(hwnd)?"true":"false",
        (unsigned long)GetWindowLongW(hwnd,GWL_STYLE),(unsigned long)GetWindowLongW(hwnd,GWL_EXSTYLE),
        r.left,r.top,r.right,r.bottom,sent?"true":"false",(unsigned long)error,(unsigned long)elapsed);
    return TRUE;
}
int main(int argc,char **argv){
    if(argc==2 && !strcmp(argv[1],"--debug-guard"))return 0;
    if(argc!=5 || strlen(argv[2])!=32 || (strcmp(argv[4],"basic")&&strcmp(argv[4],"deep")))return 2;
    for(int i=0;i<32;i++)if(!strchr("0123456789abcdef",argv[2][i]))return 2;
    char *end;target=strtoul(argv[1],&end,10);if(!target||*end || target==GetCurrentProcessId())return 2;
    char *creationEnd;unsigned long long expectedCreation=strtoull(argv[3],&creationEnd,10);if(!expectedCreation||*creationEnd)return 2;
    wchar_t destination[MAX_PATH],temporary[MAX_PATH];
    swprintf(destination,MAX_PATH,L"C:\\winlator-nvda\\config\\game-probe-%hs.json",argv[2]);
    swprintf(temporary,MAX_PATH,L"%ls.tmp",destination);out=_wfopen(temporary,L"wb");if(!out)return 3;
    DWORD began=GetTickCount();HANDLE process=OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ|SYNCHRONIZE,FALSE,target);DWORD openError=process?0:GetLastError();
    FILETIME utc;GetSystemTimeAsFileTime(&utc);
    unsigned long long epoch=(number(utc)-116444736000000000ull)/10000ull;
    fprintf(out,"{\"version\":1,\"id\":\"%s\",\"pid\":%lu,\"observerBits\":32,\"processOpened\":%s,\"openError\":%lu,\"timeMs\":%llu",argv[2],(unsigned long)target,process?"true":"false",(unsigned long)openError,epoch);
    if(process){
        FILETIME created={0},ended={0},kernel={0},user={0};SetLastError(0);BOOL got=GetProcessTimes(process,&created,&ended,&kernel,&user);DWORD error=got?0:GetLastError();
        DWORD code=0;BOOL exitOk=GetExitCodeProcess(process,&code);
        fprintf(out,",\"timesOk\":%s,\"timesError\":%lu,\"creationTime\":%llu,\"kernelTicks\":%llu,\"userTicks\":%llu,\"signaled\":%s,\"exitCode\":%lu",
            got?"true":"false",(unsigned long)error,number(created),number(kernel),number(user),WaitForSingleObject(process,0)==WAIT_OBJECT_0?"true":"false",exitOk?(unsigned long)code:0ul);
        if(!got || number(created)!=expectedCreation || WaitForSingleObject(process,0)!=WAIT_TIMEOUT){
            fprintf(out,",\"identityRejected\":true}");CloseHandle(process);fclose(out);
            return MoveFileExW(temporary,destination,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)?0:4;
        }
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
            moduleList[moduleCount++]=item;
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
            if(item.th32OwnerProcessID==target){tids[threadCount++]=item.th32ThreadID;if(count++)fputc(',',out);fprintf(out,"%lu",(unsigned long)item.th32ThreadID);}
            found=Thread32Next(snapshot,&item);
        }
        CloseHandle(snapshot);
    }
    fprintf(out,"],\"windows\":[");SetLastError(0);BOOL enumerated=EnumWindows(window,0);DWORD windowError=enumerated?0:GetLastError();
    fprintf(out,"],\"windowEnumerationOk\":%s,\"windowEnumerationError\":%lu",enumerated?"true":"false",(unsigned long)windowError);
    if(process && unresponsive && moduleError==0 && !strcmp(argv[4],"deep"))debug_snapshot(process);
    fprintf(out,",\"elapsedMs\":%lu}",(unsigned long)(GetTickCount()-began));
    if(process)CloseHandle(process);
    fclose(out);if(!MoveFileExW(temporary,destination,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))return 4;
    return 0;
}
