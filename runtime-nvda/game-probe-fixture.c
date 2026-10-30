/* SPDX-License-Identifier: MIT. CI only: responsive/blocked hidden PE32 window. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdio.h>
#include <string.h>
static LRESULT CALLBACK procedure(HWND hwnd,UINT message,WPARAM wp,LPARAM lp){
    if(message==WM_DESTROY){PostQuitMessage(0);return 0;}
    return DefWindowProcW(hwnd,message,wp,lp);
}
int WINAPI WinMain(HINSTANCE instance,HINSTANCE previous,LPSTR command,int show){
    (void)previous;(void)show;
    WNDCLASSW cls={0};cls.hInstance=instance;cls.lpfnWndProc=procedure;cls.lpszClassName=L"ProbeFixture";
    RegisterClassW(&cls);HWND hwnd=CreateWindowW(cls.lpszClassName,L"Private fixture caption",WS_OVERLAPPEDWINDOW,0,0,400,300,NULL,NULL,instance,NULL);
    FILE *output=fopen("C:\\winlator-nvda\\config\\probe-fixture.json","wb");if(!output)return 2;
    fprintf(output,"{\"pid\":%lu,\"hwnd\":%lu}",(unsigned long)GetCurrentProcessId(),(unsigned long)(ULONG_PTR)hwnd);fclose(output);
    if(strstr(command,"blocked"))Sleep(20000);
    MSG message;while(GetMessageW(&message,NULL,0,0)>0){TranslateMessage(&message);DispatchMessageW(&message);}
    return 0;
}
