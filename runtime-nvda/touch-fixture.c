/* SPDX-License-Identifier: MIT. A real Win32 UI, only built by the test workflow. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdio.h>

static int activated;
static HWND list, edit, check;
static void snapshot(HWND window) {
    WCHAR text[80]; GetWindowTextW(edit,text,80);
    char utf8[400]; WideCharToMultiByte(CP_UTF8,0,text,-1,utf8,sizeof(utf8),NULL,NULL);
    /* Fixture input is a fixed test string, never user data. */
    FILE *out=fopen("C:\\winlator-nvda\\touch-fixture.json.tmp","w");
    if (!out) return;
    fprintf(out,"{\"selected\":%d,\"focus\":%d,\"activated\":%d,\"checked\":%d,\"text\":\"%s\"}",
        (int)SendMessageW(list,LB_GETCURSEL,0,0),GetDlgCtrlID(GetFocus()),activated,
        SendMessageW(check,BM_GETCHECK,0,0)==BST_CHECKED,utf8);
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
        SetTimer(w,1,80,NULL);return 0;
    }
    if(msg==WM_COMMAND && LOWORD(wp)==1 && HIWORD(wp)==BN_CLICKED) {activated++;snapshot(w);return 0;}
    if(msg==WM_TIMER) {snapshot(w);return 0;}
    if(msg==WM_DESTROY) {PostQuitMessage(0);return 0;}
    return DefWindowProcW(w,msg,wp,lp);
}
int WINAPI WinMain(HINSTANCE instance,HINSTANCE previous,LPSTR command,int show) {
    (void)previous;(void)command;(void)show;
    WNDCLASSW cls={0};cls.hInstance=instance;cls.lpfnWndProc=procedure;cls.lpszClassName=L"NvdaTouchFixture";
    cls.hCursor=LoadCursor(NULL,IDC_ARROW);RegisterClassW(&cls);
    HWND w=CreateWindowW(cls.lpszClassName,L"NVDA touch navigation test",WS_OVERLAPPEDWINDOW|WS_VISIBLE,
        40,40,410,350,NULL,NULL,instance,NULL);
    ShowWindow(w,SW_SHOW);SetForegroundWindow(w);SetFocus(list);
    MSG msg;while(GetMessageW(&msg,NULL,0,0)>0) {
        if(!IsDialogMessageW(w,&msg)) {TranslateMessage(&msg);DispatchMessageW(&msg);}
    }
    return 0;
}
