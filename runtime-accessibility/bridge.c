/* SPDX-License-Identifier: MIT
 * Wine guest accessibility client. No injection and no screen-coordinate clicks.
 * Build with MinGW-w64; the Android host owns the authenticated loopback socket.
 */
#define COBJMACROS
#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
#include <oleacc.h>
#include <oleauto.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#define MAX_NODES 256
#define MAX_TEXT 2048
#define MAX_FRAME (1024 * 1024)
#define MAX_WINDOWS 64
#define MAX_DEPTH 12

typedef struct {
    HWND hwnd;
    IAccessible *acc;
    LONG child, role, state;
    BOOL native, actionable, editable, password;
    WCHAR name[MAX_TEXT], value[MAX_TEXT];
} Node;
static Node nodes[MAX_NODES];
static int node_count;
static HWND foreground;
static unsigned revision;
static char previous[MAX_FRAME], payload[MAX_FRAME];
static size_t used;
static BOOL overflow;
static DWORD scan_start;
static int last_result; /* 0 idle, 1 success, 2 unavailable, 3 stale, 4 unsupported */

static void append(const char *s) {
    size_t n = strlen(s);
    if (used + n + 1 >= sizeof(payload)) { overflow = TRUE; return; }
    memcpy(payload + used, s, n + 1); used += n;
}
static void number(long long n) { char s[40]; snprintf(s, sizeof(s), "%lld", n); append(s); }
static void string(const WCHAR *w) {
    char utf8[MAX_TEXT * 4];
    if (!WideCharToMultiByte(CP_UTF8, 0, w, -1, utf8, sizeof(utf8), NULL, NULL)) utf8[0] = 0;
    append("\"");
    for (const unsigned char *p = (const unsigned char *)utf8; *p; ++p) {
        char c[8];
        if (*p == '"' || *p == '\\') { c[0] = '\\'; c[1] = *p; c[2] = 0; }
        else if (*p < 32) snprintf(c, sizeof(c), "\\u%04x", *p);
        else { c[0] = *p; c[1] = 0; }
        append(c);
    }
    append("\"");
}
static VARIANT child_variant(LONG id) { VARIANT v; VariantInit(&v); V_VT(&v) = VT_I4; V_I4(&v) = id; return v; }
static void copy_bstr(WCHAR *out, BSTR s) {
    if (!s) return;
    wcsncpy(out, s, MAX_TEXT - 1); out[MAX_TEXT - 1] = 0; SysFreeString(s);
}
static void clear_nodes(void) {
    for (int i = 0; i < node_count; ++i) if (nodes[i].acc) IAccessible_Release(nodes[i].acc);
    memset(nodes, 0, sizeof(nodes)); node_count = 0;
}
static BOOL budget(void) { return node_count < MAX_NODES && GetTickCount() - scan_start < 1500; }
static BOOL is_edit(HWND w) { WCHAR c[80]; GetClassNameW(w, c, 80); return !lstrcmpiW(c, L"Edit") || !wcsnicmp(c, L"RichEdit", 8); }
static BOOL is_password(HWND w) { return is_edit(w) && (GetWindowLongPtrW(w, GWL_STYLE) & ES_PASSWORD); }
static BOOL message(HWND w, UINT m, WPARAM wp, LPARAM lp, DWORD_PTR *result) {
    return SendMessageTimeoutW(w, m, wp, lp, SMTO_ABORTIFHUNG | SMTO_BLOCK, 250, result) != 0;
}
static void window_text(HWND w, WCHAR *out) {
    DWORD_PTR result = 0;
    out[0] = 0;
    message(w, WM_GETTEXT, MAX_TEXT, (LPARAM)out, &result);
    out[MAX_TEXT - 1] = 0;
}
static LONG native_role(HWND w) {
    WCHAR c[80]; GetClassNameW(w, c, 80);
    if (is_edit(w)) return ROLE_SYSTEM_TEXT;
    if (!lstrcmpiW(c, L"Button")) {
        LONG style = GetWindowLongW(w, GWL_STYLE) & BS_TYPEMASK;
        if (style == BS_CHECKBOX || style == BS_AUTOCHECKBOX || style == BS_3STATE || style == BS_AUTO3STATE) return ROLE_SYSTEM_CHECKBUTTON;
        if (style == BS_RADIOBUTTON || style == BS_AUTORADIOBUTTON) return ROLE_SYSTEM_RADIOBUTTON;
        if (style == BS_GROUPBOX) return ROLE_SYSTEM_GROUPING;
        return ROLE_SYSTEM_PUSHBUTTON;
    }
    if (!lstrcmpiW(c, L"Static")) return ROLE_SYSTEM_STATICTEXT;
    if (!lstrcmpiW(c, L"ComboBox")) return ROLE_SYSTEM_COMBOBOX;
    if (!lstrcmpiW(c, L"ListBox") || !lstrcmpiW(c, L"SysListView32")) return ROLE_SYSTEM_LIST;
    if (!lstrcmpiW(c, L"SysTreeView32")) return ROLE_SYSTEM_OUTLINE;
    return 0;
}
static BOOL add_accessible(IAccessible *acc, LONG child, HWND owner) {
    if (!budget()) return FALSE;
    VARIANT v = child_variant(child), role, state;
    VariantInit(&role); VariantInit(&state);
    IAccessible_get_accRole(acc, v, &role);
    IAccessible_get_accState(acc, v, &state);
    LONG r = V_VT(&role) == VT_I4 ? V_I4(&role) : ROLE_SYSTEM_CLIENT;
    LONG s = V_VT(&state) == VT_I4 ? V_I4(&state) : 0;
    VariantClear(&role); VariantClear(&state);
    if (s & (STATE_SYSTEM_INVISIBLE | STATE_SYSTEM_OFFSCREEN)) return FALSE;
    Node n; memset(&n, 0, sizeof(n)); n.role = r; n.state = s; n.child = child;
    n.hwnd = owner;
    HWND found = NULL;
    if (SUCCEEDED(WindowFromAccessibleObject(acc, &found)) && found) n.hwnd = found;
    n.password = (s & STATE_SYSTEM_PROTECTED) || is_password(n.hwnd);
    BSTR text = NULL;
    if (SUCCEEDED(IAccessible_get_accName(acc, v, &text))) copy_bstr(n.name, text);
    if (!n.password) {
        text = NULL;
        if (SUCCEEDED(IAccessible_get_accValue(acc, v, &text))) copy_bstr(n.value, text);
    }
    text = NULL;
    if (SUCCEEDED(IAccessible_get_accDefaultAction(acc, v, &text)) && text) {
        n.actionable = SysStringLen(text) > 0; SysFreeString(text);
    }
    n.editable = r == ROLE_SYSTEM_TEXT && !(s & STATE_SYSTEM_READONLY) && !n.password;
    /* Empty container nodes add noise; always traverse their children below. */
    if (!n.name[0] && !n.value[0] && !n.actionable && !n.editable && !n.password) return FALSE;
    IAccessible_AddRef(acc); n.acc = acc; nodes[node_count++] = n;
    return TRUE;
}
static void walk_accessible(IAccessible *acc, int depth, HWND owner) {
    if (depth > MAX_DEPTH || !budget()) return;
    add_accessible(acc, CHILDID_SELF, owner);
    LONG count = 0;
    if (FAILED(IAccessible_get_accChildCount(acc, &count)) || count <= 0) return;
    if (count > MAX_NODES) count = MAX_NODES;
    VARIANT children[MAX_NODES];
    for (int i = 0; i < count; ++i) VariantInit(&children[i]);
    LONG got = 0;
    HRESULT hr = AccessibleChildren(acc, 0, count, children, &got);
    if (SUCCEEDED(hr)) for (int i = 0; i < got && budget(); ++i) {
        if (V_VT(&children[i]) == VT_I4) {
            LONG id = V_I4(&children[i]);
            if (id != CHILDID_SELF) add_accessible(acc, id, owner);
        } else if (V_VT(&children[i]) == VT_DISPATCH && V_DISPATCH(&children[i])) {
            IAccessible *child = NULL;
            if (SUCCEEDED(IDispatch_QueryInterface(V_DISPATCH(&children[i]), &IID_IAccessible, (void **)&child))) {
                if (child != acc) walk_accessible(child, depth + 1, owner);
                IAccessible_Release(child);
            }
        }
    }
    for (int i = 0; i < count; ++i) VariantClear(&children[i]);
}
static BOOL CALLBACK native_child(HWND w, LPARAM ignored) {
    (void)ignored;
    if (!budget()) return FALSE;
    if (!IsWindowVisible(w)) return TRUE;
    LONG role = native_role(w);
    if (!role) return TRUE;
    for (int i = 0; i < node_count; ++i)
        if (nodes[i].hwnd == w && nodes[i].child == CHILDID_SELF && nodes[i].role == role) return TRUE;
    Node n; memset(&n, 0, sizeof(n)); n.hwnd = w; n.native = TRUE; n.role = role;
    n.password = is_password(w);
    if (!IsWindowEnabled(w)) n.state |= STATE_SYSTEM_UNAVAILABLE;
    if (GetFocus() == w) n.state |= STATE_SYSTEM_FOCUSED;
    if (role == ROLE_SYSTEM_CHECKBUTTON || role == ROLE_SYSTEM_RADIOBUTTON) {
        DWORD_PTR checked = 0;
        if (message(w, BM_GETCHECK, 0, 0, &checked) && checked == BST_CHECKED) n.state |= STATE_SYSTEM_CHECKED;
    }
    n.actionable = role == ROLE_SYSTEM_PUSHBUTTON || role == ROLE_SYSTEM_CHECKBUTTON || role == ROLE_SYSTEM_RADIOBUTTON;
    n.editable = is_edit(w) && !(GetWindowLongPtrW(w, GWL_STYLE) & ES_READONLY) && !n.password;
    if (role == ROLE_SYSTEM_TEXT) {
        if (!n.password) window_text(w, n.value);
        HWND label = GetWindow(w, GW_HWNDPREV);
        WCHAR c[80]; GetClassNameW(label, c, 80);
        if (!lstrcmpiW(c, L"Static")) window_text(label, n.name);
    } else window_text(w, n.name);
    if (!n.name[0] && !n.value[0] && !n.actionable && !n.editable && !n.password) return TRUE;
    nodes[node_count++] = n;
    return TRUE;
}
static BOOL eligible_window(HWND w) {
    if (!IsWindowVisible(w)) return FALSE;
    WCHAR title[MAX_TEXT]; GetWindowTextW(w, title, MAX_TEXT);
    return title[0] != 0;
}
static BOOL CALLBACK window_json(HWND w, LPARAM context) {
    int *count = (int *)context;
    if (*count >= MAX_WINDOWS) return FALSE;
    if (!eligible_window(w)) return TRUE;
    WCHAR title[MAX_TEXT]; GetWindowTextW(w, title, MAX_TEXT);
    if ((*count)++) append(",");
    append("{\"id\":\""); char id[32]; snprintf(id, sizeof(id), "%llx", (unsigned long long)(uintptr_t)w); append(id);
    append("\",\"name\":"); string(title); append("}"); return TRUE;
}
static void snapshot(void) {
    clear_nodes(); scan_start = GetTickCount();
    foreground = GetForegroundWindow();
    if (foreground) {
        IAccessible *root = NULL;
        if (SUCCEEDED(AccessibleObjectFromWindow(foreground, OBJID_CLIENT, &IID_IAccessible, (void **)&root))) {
            walk_accessible(root, 0, foreground); IAccessible_Release(root);
        }
        EnumChildWindows(foreground, native_child, 0);
    }
    used = 0; overflow = FALSE; payload[0] = 0;
    WCHAR title[MAX_TEXT] = L""; if (foreground) GetWindowTextW(foreground, title, MAX_TEXT);
    append("\"title\":"); string(title); append(",\"window\":\"");
    char handle[32]; snprintf(handle, sizeof(handle), "%llx", (unsigned long long)(uintptr_t)foreground); append(handle);
    append("\",\"windows\":["); int count = 0; EnumWindows(window_json, (LPARAM)&count); append("],\"nodes\":[");
    for (int i = 0; i < node_count; ++i) {
        Node *n = &nodes[i]; if (i) append(",");
        append("{\"id\":"); number(i + 1); append(",\"role\":"); number(n->role);
        append(",\"state\":"); number(n->state); append(",\"name\":"); string(n->name);
        append(",\"value\":"); string(n->value);
        append(",\"click\":"); append(n->actionable ? "true" : "false");
        append(",\"edit\":"); append(n->editable ? "true" : "false");
        append(",\"password\":"); append(n->password ? "true" : "false");
        append(",\"source\":"); append(n->native ? "\"win32\"" : "\"msaa\""); append("}");
    }
    append("],\"limited\":"); append(node_count == MAX_NODES || GetTickCount() - scan_start >= 1500 ? "true" : "false");
    if (overflow) { strcpy(payload, "\"title\":\"\",\"window\":\"0\",\"windows\":[],\"nodes\":[],\"limited\":true"); }
    if (strcmp(previous, payload)) { ++revision; strcpy(previous, payload); }
}
static BOOL transfer(SOCKET s, char *buffer, int length, BOOL sending) {
    while (length > 0) {
        int n = sending ? send(s, buffer, length, 0) : recv(s, buffer, length, 0);
        if (n <= 0) return FALSE;
        buffer += n; length -= n;
    }
    return TRUE;
}
static BOOL send_frame(SOCKET s, const char *data) {
    uint32_t size = htonl((uint32_t)strlen(data));
    return transfer(s, (char *)&size, 4, TRUE) && transfer(s, (char *)data, (int)strlen(data), TRUE);
}
static BOOL read_frame(SOCKET s, char *data, int capacity) {
    uint32_t size;
    if (!transfer(s, (char *)&size, 4, FALSE)) return FALSE;
    size = ntohl(size);
    if (!size || size >= (uint32_t)capacity) return FALSE;
    if (!transfer(s, data, (int)size, FALSE)) return FALSE;
    data[size] = 0; return TRUE;
}
static BOOL activate(HWND w) {
    if (!IsWindow(w)) return FALSE;
    HWND root = GetAncestor(w, GA_ROOT);
    ShowWindow(root, SW_RESTORE); SetForegroundWindow(root);
    return GetForegroundWindow() == root;
}
static BOOL focus_window(HWND w) {
    if (!activate(w)) return FALSE;
    DWORD target = GetWindowThreadProcessId(w, NULL), self = GetCurrentThreadId();
    BOOL attached = target != self && AttachThreadInput(self, target, TRUE);
    SetFocus(w); BOOL ok = GetFocus() == w;
    if (attached) AttachThreadInput(self, target, FALSE);
    return ok;
}
static BOOL decode_text(const char *hex, WCHAR *out) {
    size_t len = strlen(hex); char utf8[MAX_TEXT * 4];
    if (len % 2 || len >= sizeof(utf8) * 2) return FALSE;
    for (size_t i = 0; i < len / 2; ++i) {
        char pair[3] = {hex[2*i], hex[2*i+1], 0}, *end = NULL;
        unsigned long b = strtoul(pair, &end, 16);
        if (end != pair + 2 || !b) return FALSE;
        utf8[i] = (char)b;
    }
    utf8[len/2] = 0;
    return MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, utf8, -1, out, MAX_TEXT) != 0;
}
static int act(unsigned rev, int id, const char *verb, const char *text) {
    if (rev != revision || GetForegroundWindow() != foreground) return 3;
    if (id < 1 || id > node_count) return 2;
    Node *n = &nodes[id-1];
    if (!IsWindow(n->hwnd) || !IsWindowEnabled(n->hwnd) || !IsWindowVisible(n->hwnd) || (n->state & STATE_SYSTEM_UNAVAILABLE)) return 2;
    VARIANT v = child_variant(n->child); DWORD_PTR result = 0;
    if (!strcmp(verb, "click") && n->actionable) {
        if (n->acc) return SUCCEEDED(IAccessible_accDoDefaultAction(n->acc, v)) ? 1 : 2;
        return message(n->hwnd, BM_CLICK, 0, 0, &result) ? 1 : 2;
    }
    if (!strcmp(verb, "edit") && n->editable && !n->password && !is_password(n->hwnd)) {
        WCHAR value[MAX_TEXT]; if (!decode_text(text, value)) return 4;
        if (n->acc) {
            BSTR b = SysAllocString(value); if (!b) return 2;
            HRESULT hr = IAccessible_put_accValue(n->acc, v, b); SysFreeString(b);
            return SUCCEEDED(hr) ? 1 : 2;
        }
        return message(n->hwnd, WM_SETTEXT, 0, (LPARAM)value, &result) && result ? 1 : 2;
    }
    if (!strcmp(verb, "focus")) {
        if (n->acc && SUCCEEDED(IAccessible_accSelect(n->acc, SELFLAG_TAKEFOCUS, v))) return 1;
        return n->native && focus_window(n->hwnd) ? 1 : 2;
    }
    return 4;
}
static int keyboard(unsigned rev, const char *key) {
    if (rev != revision || GetForegroundWindow() != foreground) return 3;
    WORD vk = 0; BOOL shift = FALSE;
    if (!strcmp(key, "tab")) vk = VK_TAB;
    else if (!strcmp(key, "backtab")) { vk = VK_TAB; shift = TRUE; }
    else if (!strcmp(key, "enter")) vk = VK_RETURN;
    else if (!strcmp(key, "escape")) vk = VK_ESCAPE;
    else if (!strcmp(key, "up")) vk = VK_UP;
    else if (!strcmp(key, "down")) vk = VK_DOWN;
    else if (!strcmp(key, "left")) vk = VK_LEFT;
    else if (!strcmp(key, "right")) vk = VK_RIGHT;
    else if (!strcmp(key, "space")) vk = VK_SPACE;
    if (!vk || !foreground) return 4;
    INPUT in[4]; memset(in, 0, sizeof(in)); int count = 0;
    if (shift) { in[count].type = INPUT_KEYBOARD; in[count++].ki.wVk = VK_SHIFT; }
    in[count].type = INPUT_KEYBOARD; in[count++].ki.wVk = vk;
    in[count].type = INPUT_KEYBOARD; in[count].ki.wVk = vk; in[count++].ki.dwFlags = KEYEVENTF_KEYUP;
    if (shift) { in[count].type = INPUT_KEYBOARD; in[count].ki.wVk = VK_SHIFT; in[count++].ki.dwFlags = KEYEVENTF_KEYUP; }
    return SendInput(count, in, sizeof(INPUT)) == (UINT)count ? 1 : 2;
}

/* A real Win32 fixture used both on-device and by the Wine integration test. */
static LRESULT CALLBACK fixture_proc(HWND w, UINT msg, WPARAM wp, LPARAM lp) {
    if (msg == WM_CREATE) {
        HINSTANCE instance = GetModuleHandleW(NULL);
        CreateWindowW(L"Static", L"Tên thử", WS_CHILD|WS_VISIBLE, 12,12,400,24,w,(HMENU)100,instance,NULL);
        CreateWindowW(L"Edit", L"", WS_CHILD|WS_VISIBLE|WS_TABSTOP|WS_BORDER|ES_AUTOHSCROLL,12,40,400,32,w,(HMENU)101,instance,NULL);
        CreateWindowW(L"Button", L"Đồng ý", WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_AUTOCHECKBOX,12,84,400,32,w,(HMENU)102,instance,NULL);
        CreateWindowW(L"Button", L"Tiếp tục", WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_PUSHBUTTON,12,128,190,40,w,(HMENU)103,instance,NULL);
        CreateWindowW(L"Static", L"Chưa kích hoạt", WS_CHILD|WS_VISIBLE,12,184,400,30,w,(HMENU)104,instance,NULL);
        CreateWindowW(L"Static", L"Mật khẩu", WS_CHILD|WS_VISIBLE,12,224,400,24,w,(HMENU)105,instance,NULL);
        CreateWindowW(L"Edit", L"SECRET_MUST_NOT_LEAK", WS_CHILD|WS_VISIBLE|WS_TABSTOP|WS_BORDER|ES_PASSWORD,12,254,400,32,w,(HMENU)106,instance,NULL);
        CreateWindowW(L"Button", L"Disabled control", WS_CHILD|WS_VISIBLE|WS_DISABLED|BS_PUSHBUTTON,12,300,190,32,w,(HMENU)107,instance,NULL);
        return 0;
    }
    if (msg == WM_COMMAND && LOWORD(wp) == 103 && HIWORD(wp) == BN_CLICKED) {
        SetWindowTextW(GetDlgItem(w,104), L"Đã kích hoạt"); return 0;
    }
    if (msg == WM_DESTROY) { PostQuitMessage(0); return 0; }
    return DefWindowProcW(w,msg,wp,lp);
}
static int fixture(void) {
    WNDCLASSW cls; memset(&cls,0,sizeof(cls)); cls.lpfnWndProc=fixture_proc;
    cls.hInstance=GetModuleHandleW(NULL); cls.lpszClassName=L"WinlatorA11yFixture";
    cls.hCursor=LoadCursor(NULL,IDC_ARROW); cls.hbrBackground=(HBRUSH)(COLOR_WINDOW+1); RegisterClassW(&cls);
    HWND w=CreateWindowW(cls.lpszClassName,L"Winlator accessibility test",WS_OVERLAPPEDWINDOW|WS_VISIBLE,80,80,460,410,NULL,NULL,cls.hInstance,NULL);
    if (!w) return 1;
    SetForegroundWindow(w); MSG msg;
    while (GetMessageW(&msg,NULL,0,0)>0) { if (!IsDialogMessageW(w,&msg)) { TranslateMessage(&msg); DispatchMessageW(&msg); } }
    return 0;
}
static int launch_fixture(void) {
    WCHAR exe[32768], cmd[32768]; GetModuleFileNameW(NULL,exe,32768);
    if (wcslen(exe)>32000) return 2;
    swprintf(cmd,32768,L"\"%ls\" --fixture",exe);
    STARTUPINFOW si; PROCESS_INFORMATION pi; memset(&si,0,sizeof(si)); si.cb=sizeof(si);
    if (!CreateProcessW(NULL,cmd,NULL,NULL,FALSE,0,NULL,NULL,&si,&pi)) return 2;
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess); return 1;
}
int main(int argc, char **argv) {
    if (argc==2 && !strcmp(argv[1],"--fixture")) return fixture();
    if (argc!=3 || strlen(argv[2])!=32 || strspn(argv[2],"0123456789abcdef")!=32) return 2;
    char *end=NULL; long port=strtol(argv[1],&end,10);
    if (!end || *end || port<1024 || port>65535) return 2;
    WSADATA ws; if (WSAStartup(MAKEWORD(2,2),&ws)) return 3;
    HRESULT com=CoInitializeEx(NULL,COINIT_APARTMENTTHREADED);
    if (FAILED(com)) { WSACleanup(); return 3; }
    SOCKET sock=socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);
    struct sockaddr_in addr; memset(&addr,0,sizeof(addr)); addr.sin_family=AF_INET;
    addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK); addr.sin_port=htons((u_short)port);
    DWORD timeout=120000; setsockopt(sock,SOL_SOCKET,SO_RCVTIMEO,(char *)&timeout,sizeof(timeout));
    setsockopt(sock,SOL_SOCKET,SO_SNDTIMEO,(char *)&timeout,sizeof(timeout));
    if (connect(sock,(struct sockaddr *)&addr,sizeof(addr))) { closesocket(sock); CoUninitialize(); WSACleanup(); return 4; }
    char hello[80]; snprintf(hello,sizeof(hello),"WINLATOR-A11Y-1 %s",argv[2]);
    if (!send_frame(sock,hello)) { closesocket(sock); CoUninitialize(); WSACleanup(); return 4; }
    char command[20000];
    while (read_frame(sock,command,sizeof(command))) {
        if (!strcmp(command,"quit")) break;
        last_result=0;
        if (!strcmp(command,"snapshot")) { /* no action */ }
        else if (!strcmp(command,"test")) last_result=launch_fixture();
        else if (!strncmp(command,"window\t",7)) {
            char *tail=NULL; uintptr_t id=(uintptr_t)strtoull(command+7,&tail,16);
            last_result=tail && !*tail && eligible_window((HWND)id) && activate((HWND)id) ? 1:2;
        } else if (!strncmp(command,"key\t",4)) {
            unsigned rev=0; char key[20]={0};
            last_result=sscanf(command+4,"%u\t%19s",&rev,key)==2 ? keyboard(rev,key):4;
        } else if (!strncmp(command,"act\t",4)) {
            unsigned rev=0; int id=0, offset=0; char verb[16]={0};
            if (sscanf(command+4,"%u\t%d\t%15[^\t]\t%n",&rev,&id,verb,&offset)>=3 && offset)
                last_result=act(rev,id,verb,command+4+offset);
            else last_result=4;
        } else last_result=4;
        Sleep(40); snapshot();
        static char frame[MAX_FRAME+128];
        snprintf(frame,sizeof(frame),"{\"version\":1,\"revision\":%u,\"result\":%d,%s}",revision,last_result,payload);
        if (!send_frame(sock,frame)) break;
    }
    clear_nodes(); closesocket(sock); CoUninitialize(); WSACleanup(); return 0;
}
