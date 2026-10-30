/* SPDX-License-Identifier: MIT. CI only: sentinel ABI and error preservation. */
#define UNICODE
#include <windows.h>
#include <wchar.h>
#include <string.h>
int __stdcall fixtureInitA(void *a,void *b){SetLastError(321);return a==(void*)17&&b==(void*)29?73:0;}
int __stdcall fixtureInitW(void *a,void *b){SetLastError(322);return a==(void*)17&&b==(void*)29?74:0;}
int __stdcall fixtureSpeakA(const char *t){SetLastError(323);return t?(int)strlen(t)+100:0;}
int __stdcall fixtureSpeakW(const wchar_t *t){SetLastError(324);return t?(int)wcslen(t)+200:0;}
int __stdcall fixtureNotify(void *a,void *b,void *c){return a==(void*)1&&b==(void*)2&&c==(void*)3?81:0;}
int __stdcall fixtureUninit(void *a){return a==(void*)31?82:0;}
int __stdcall fixtureNoArgs(void){SetLastError(325);return 715;}
