/* SPDX-License-Identifier: MIT. A real Win32 UI, only built by the test workflow. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <commctrl.h>
#include <commdlg.h>

static int activated,last_key,control_seen,custom_mode;
static HWND list, edit, check, combo, radio, slider;
static void snapshot(HWND window) {
    WCHAR text[80]; GetWindowTextW(edit,text,80);
    char utf8[400]; WideCharToMultiByte(CP_UTF8,0,text,-1,utf8,sizeof(utf8),NULL,NULL);
    /* Fixture input is a fixed test string, never user data. */
    FILE *out=fopen("C:\\winlator-nvda\\touch-fixture.json.tmp","w");
    if (!out) return;
    fprintf(out,"{\"selected\":%d,\"focus\":%d,\"activated\":%d,\"checked\":%d,\"text\":\"%s\",\"lastKey\":%d,\"controlSeen\":%d}",
        (int)SendMessageW(list,LB_GETCURSEL,0,0),GetDlgCtrlID(GetFocus()),activated,
        SendMessageW(check,BM_GETCHECK,0,0)==BST_CHECKED,utf8,last_key,control_seen);
    fclose(out);
    MoveFileExW(L"C:\\winlator-nvda\\touch-fixture.json.tmp",L"C:\\winlator-nvda\\touch-fixture.json",MOVEFILE_REPLACE_EXISTING);
    (void)window;
}
static LRESULT CALLBACK procedure(HWND w,UINT msg,WPARAM wp,LPARAM lp) {
    if(msg==WM_CREATE) {
        HINSTANCE instance=((LPCREATESTRUCT)lp)->hInstance;
        list=CreateWindowW(L"ListBox",L"",WS_VISIBLE|WS_CHILD|WS_TABSTOP|WS_BORDER|LBS_NOTIFY,
            12,12,360,100,w,(HMENU)101,instance,NULL);
        SendMessageW(list,LB_ADDSTRING,0,(LPARAM)L"Alpha");
        SendMessageW(list,LB_ADDSTRING,0,(LPARAM)L"Beta");
        SendMessageW(list,LB_ADDSTRING,0,(LPARAM)L"Gamma");
        SendMessageW(list,LB_SETCURSEL,0,0);
        CreateWindowW(L"Button",L"Activate test",WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_DEFPUSHBUTTON,
            12,120,360,34,w,(HMENU)1,instance,NULL);
        check=CreateWindowW(L"Button",L"Test checkbox",WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_AUTOCHECKBOX,
            12,164,360,34,w,(HMENU)102,instance,NULL);
        edit=CreateWindowW(L"Edit",L"",WS_CHILD|WS_VISIBLE|WS_TABSTOP|WS_BORDER|ES_AUTOHSCROLL,
            12,210,360,34,w,(HMENU)103,instance,NULL);
        CreateWindowW(L"Edit",L"SECRET_MUST_NOT_LEAK",WS_CHILD|WS_VISIBLE|WS_TABSTOP|WS_BORDER|ES_PASSWORD,
            12,254,360,34,w,(HMENU)104,instance,NULL);
        combo=CreateWindowW(L"ComboBox",L"",WS_CHILD|WS_VISIBLE|WS_TABSTOP|CBS_DROPDOWNLIST,
            12,294,360,120,w,(HMENU)105,instance,NULL);
        SendMessageW(combo,CB_ADDSTRING,0,(LPARAM)L"Option Alpha");
        SendMessageW(combo,CB_ADDSTRING,0,(LPARAM)L"Option Beta");
        SendMessageW(combo,CB_SETCURSEL,0,0);
        radio=CreateWindowW(L"Button",L"Test radio",WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_AUTORADIOBUTTON,
            12,334,360,30,w,(HMENU)106,instance,NULL);
        slider=CreateWindowW(TRACKBAR_CLASSW,L"Test slider",WS_CHILD|WS_VISIBLE|WS_TABSTOP,
            12,374,360,30,w,(HMENU)107,instance,NULL);
        SendMessageW(slider,TBM_SETRANGE,TRUE,MAKELPARAM(0,100));
        SendMessageW(slider,TBM_SETPOS,TRUE,50);
        CreateWindowW(L"Button",L"Open message dialog",WS_CHILD|WS_VISIBLE|WS_TABSTOP,
            12,414,360,30,w,(HMENU)108,instance,NULL);
        CreateWindowW(L"Button",L"Open file dialog",WS_CHILD|WS_VISIBLE|WS_TABSTOP,
            12,454,360,30,w,(HMENU)109,instance,NULL);
        CreateWindowW(L"Button",L"Open popup menu",WS_CHILD|WS_VISIBLE|WS_TABSTOP,
            12,494,360,30,w,(HMENU)110,instance,NULL);
        WNDCLASSEXW forms={0};forms.cbSize=sizeof(forms);
        if(GetClassInfoExW(NULL,L"Button",&forms)) {
            forms.hInstance=instance;forms.lpszClassName=L"WindowsForms10.BUTTON.app.fixture";forms.style &= ~CS_GLOBALCLASS;
            RegisterClassExW(&forms);
            CreateWindowW(forms.lpszClassName,L"Windows Forms test",WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_PUSHBUTTON,
                12,534,360,30,w,(HMENU)111,instance,NULL);
        }
        SetTimer(w,1,80,NULL);return 0;
    }
    if(msg==WM_COMMAND && LOWORD(wp)==1 && HIWORD(wp)==BN_CLICKED) {activated++;snapshot(w);return 0;}
    if(msg==WM_COMMAND && LOWORD(wp)==108 && HIWORD(wp)==BN_CLICKED) {
        MessageBoxW(w,L"Test installation question. Continue?",L"NVDA audit question",MB_OKCANCEL);
        return 0;
    }
    if(msg==WM_COMMAND && LOWORD(wp)==109 && HIWORD(wp)==BN_CLICKED) {
        WCHAR path[MAX_PATH]=L""; OPENFILENAMEW file={0};file.lStructSize=sizeof(file);file.hwndOwner=w;
        file.lpstrFile=path;file.nMaxFile=MAX_PATH;file.lpstrTitle=L"NVDA audit choose file";
        file.Flags=OFN_FILEMUSTEXIST|OFN_NOCHANGEDIR;GetOpenFileNameW(&file);return 0;
    }
    if(msg==WM_COMMAND && LOWORD(wp)==110 && HIWORD(wp)==BN_CLICKED) {
        HMENU menu=CreatePopupMenu();AppendMenuW(menu,MF_STRING,201,L"Audit menu Alpha");
        AppendMenuW(menu,MF_STRING,202,L"Audit menu Beta");
        TrackPopupMenu(menu,TPM_RETURNCMD,60,100,0,w,NULL);DestroyMenu(menu);return 0;
    }
    if(msg==WM_TIMER) {snapshot(w);return 0;}
    if(msg==WM_DESTROY) {PostQuitMessage(0);return 0;}
    return DefWindowProcW(w,msg,wp,lp);
}
int WINAPI WinMain(HINSTANCE instance,HINSTANCE previous,LPSTR command,int show) {
    (void)previous;(void)show;custom_mode=strstr(command,"custom")!=NULL;
    INITCOMMONCONTROLSEX controls={sizeof(controls),ICC_BAR_CLASSES};InitCommonControlsEx(&controls);
    WNDCLASSW cls={0};cls.hInstance=instance;cls.lpfnWndProc=procedure;cls.lpszClassName=custom_mode?L"WTWindow":L"NvdaTouchFixture";
    cls.hCursor=LoadCursor(NULL,IDC_ARROW);RegisterClassW(&cls);
    HWND w=CreateWindowW(cls.lpszClassName,custom_mode?L"ÓïÒô¿âÅäÖÃ":L"NVDA touch navigation test",WS_OVERLAPPEDWINDOW|WS_VISIBLE,
        40,40,410,640,NULL,NULL,instance,NULL);
    ShowWindow(w,SW_SHOW);SetForegroundWindow(w);SetFocus(custom_mode?w:list);
    MSG msg;while(GetMessageW(&msg,NULL,0,0)>0) {
        if(msg.message==WM_KEYDOWN || msg.message==WM_SYSKEYDOWN) {last_key=(int)msg.wParam;control_seen=(GetKeyState(VK_CONTROL)&0x8000)!=0;snapshot(w);}
        if(custom_mode || !IsDialogMessageW(w,&msg)) {TranslateMessage(&msg);DispatchMessageW(&msg);}
    }
    return 0;
}
