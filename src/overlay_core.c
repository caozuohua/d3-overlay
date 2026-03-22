/*
 * D3OA — C 扩展模块: overlay_core.c
 *
 * 高性能 Win32 透明窗口核心功能。
 * 提供比纯 Python ctypes 更低开销的窗口操作和像素处理。
 *
 * 安全说明：
 * - 所有 API 均为标准 Win32 窗口管理接口
 * - 不读写游戏内存，不注入 DLL，不 Hook API
 * - 与 OBS、Discord Overlay 原理相同
 *
 * 编译: python setup.py build_ext --inplace
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <windows.h>
#include <dwmapi.h>

/* ─── 常量 ─────────────────────────────────────────────── */

#define OVERLAY_WS_EX (WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)

/* DPI 感知上下文常量 (Windows 10 1703+) */
#ifndef DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
#define DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 ((HANDLE)-4)
#endif

/* ─── 全局状态 ─────────────────────────────────────────── */

static HWND g_overlay_hwnd = NULL;
static HDC  g_hdc_mem = NULL;
static HBITMAP g_hbitmap = NULL;
static void *g_pixels = NULL;
static int g_width = 0;
static int g_height = 0;
static int g_visible = 0;

/* ─── DPI 感知初始化 ─────────────────────────────────── */

static void init_dpi_awareness(void) {
    /* 
     * 尝试设置 PerMonitorV2 DPI 感知 (Windows 10 1703+)
     * 这确保叠加窗口在多显示器、不同 DPI 环境下正确定位
     */
    typedef BOOL (WINAPI *SetProcessDpiAwarenessContextFunc)(HANDLE);
    HMODULE hUser32 = GetModuleHandleW(L"user32.dll");
    
    if (hUser32) {
        SetProcessDpiAwarenessContextFunc pSetCtx = 
            (SetProcessDpiAwarenessContextFunc)GetProcAddress(hUser32, "SetProcessDpiAwarenessContext");
        if (pSetCtx) {
            if (pSetCtx(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)) {
                return; /* 成功 */
            }
        }
    }

    /* 回退: shcore.SetProcessDpiAwareness (Windows 8.1+) */
    typedef enum {
        PROCESS_DPI_UNAWARE = 0,
        PROCESS_SYSTEM_DPI_AWARE = 1,
        PROCESS_PER_MONITOR_DPI_AWARE = 2
    } PROCESS_DPI_AWARENESS;

    typedef HRESULT (WINAPI *SetProcessDpiAwarenessFunc)(PROCESS_DPI_AWARENESS);
    HMODULE hShcore = LoadLibraryW(L"shcore.dll");
    
    if (hShcore) {
        SetProcessDpiAwarenessFunc pSetAwareness = 
            (SetProcessDpiAwarenessFunc)GetProcAddress(hShcore, "SetProcessDpiAwareness");
        if (pSetAwareness) {
            pSetAwareness(PROCESS_PER_MONITOR_DPI_AWARE);
        }
        FreeLibrary(hShcore);
        return;
    }

    /* 最终回退: SetProcessDPIAware (Windows Vista+) */
    SetProcessDPIAware();
}

/* ─── 窗口过程 ─────────────────────────────────────────── */

static LRESULT CALLBACK overlay_wndproc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    return DefWindowProcW(hwnd, msg, wp, lp);
}

/* ─── 创建叠加窗口 ─────────────────────────────────────── */

static PyObject* py_create_overlay(PyObject* self, PyObject* args) {
    int screen_w, screen_h;
    if (!PyArg_ParseTuple(args, "ii", &screen_w, &screen_h))
        return NULL;

    /* 初始化 DPI 感知（仅首次调用生效） */
    init_dpi_awareness();

    HINSTANCE hinst = GetModuleHandle(NULL);

    /* 使用唯一类名，避免冲突 */
    static wchar_t class_name[64];
    wsprintfW(class_name, L"D3OA_Core_%08X", GetCurrentProcessId());

    /* 注册窗口类 */
    WNDCLASSEXW wc = {0};
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = overlay_wndproc;
    wc.hInstance = hinst;
    wc.lpszClassName = class_name;

    if (!RegisterClassExW(&wc)) {
        DWORD err = GetLastError();
        if (err != ERROR_CLASS_ALREADY_EXISTS) {
            PyErr_Format(PyExc_RuntimeError, 
                "RegisterClassExW failed, GetLastError=%lu. "
                "This may indicate a security software conflict.", err);
            return NULL;
        }
    }

    /* 创建窗口 */
    HWND hwnd = CreateWindowExW(
        OVERLAY_WS_EX,
        class_name,
        L"D3OA Core",
        WS_POPUP,
        0, 0, screen_w, screen_h,
        NULL, NULL, hinst, NULL
    );

    if (!hwnd) {
        DWORD err = GetLastError();
        const char *err_desc = "Unknown error";
        switch (err) {
            case 0:   err_desc = "Possibly blocked by security software"; break;
            case 5:   err_desc = "Access denied (check UAC/security software)"; break;
            case 8:   err_desc = "Insufficient memory"; break;
            case 87:  err_desc = "Invalid parameters (DPI scaling issue?)"; break;
            case 1407: err_desc = "Window class not found"; break;
            case 1410: err_desc = "Window class already exists"; break;
        }
        PyErr_Format(PyExc_RuntimeError,
            "CreateWindowExW failed: %s (error %lu). "
            "Try: 1) Add D3OA to antivirus whitelist, "
            "2) Ensure d3oa.manifest is alongside the EXE, "
            "3) Close other overlay tools.", err_desc, err);
        return NULL;
    }

    /* 设置透明度 */
    SetLayeredWindowAttributes(hwnd, 0, 220, LWA_ALPHA);

    /* 创建渲染表面 */
    HDC hdc_screen = GetDC(NULL);
    HDC hdc_mem = CreateCompatibleDC(hdc_screen);

    BITMAPINFO bmi = {0};
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bmi.bmiHeader.biWidth = screen_w;
    bmi.bmiHeader.biHeight = -screen_h;  /* top-down */
    bmi.bmiHeader.biPlanes = 1;
    bmi.bmiHeader.biBitCount = 32;
    bmi.bmiHeader.biCompression = BI_RGB;

    void *pixels = NULL;
    HBITMAP hbmp = CreateDIBSection(hdc_mem, &bmi, DIB_RGB_COLORS, &pixels, NULL, 0);
    SelectObject(hdc_mem, hbmp);

    ReleaseDC(NULL, hdc_screen);

    /* 存储全局状态 */
    g_overlay_hwnd = hwnd;
    g_hdc_mem = hdc_mem;
    g_hbitmap = hbmp;
    g_pixels = pixels;
    g_width = screen_w;
    g_height = screen_h;
    g_visible = 0;

    return PyLong_FromVoidPtr(hwnd);
}

/* ─── 销毁叠加窗口 ─────────────────────────────────────── */

static PyObject* py_destroy_overlay(PyObject* self, PyObject* args) {
    if (g_hbitmap) { DeleteObject(g_hbitmap); g_hbitmap = NULL; }
    if (g_hdc_mem) { DeleteDC(g_hdc_mem); g_hdc_mem = NULL; }
    if (g_overlay_hwnd) { DestroyWindow(g_overlay_hwnd); g_overlay_hwnd = NULL; }
    g_pixels = NULL;
    g_visible = 0;
    Py_RETURN_NONE;
}

/* ─── 显示/隐藏 ───────────────────────────────────────── */

static PyObject* py_show(PyObject* self, PyObject* args) {
    if (g_overlay_hwnd) {
        ShowWindow(g_overlay_hwnd, SW_SHOWNOACTIVATE);
        g_visible = 1;
    }
    Py_RETURN_NONE;
}

static PyObject* py_hide(PyObject* self, PyObject* args) {
    if (g_overlay_hwnd) {
        ShowWindow(g_overlay_hwnd, SW_HIDE);
        g_visible = 0;
    }
    Py_RETURN_NONE;
}

/* ─── 同步到游戏窗口 ──────────────────────────────────── */

static PyObject* py_sync_to_game(PyObject* self, PyObject* args) {
    HWND game_hwnd = FindWindowW(L"D3 Main Window Class", NULL);
    if (!game_hwnd) {
        Py_RETURN_FALSE;
    }

    RECT rect;
    GetWindowRect(game_hwnd, &rect);
    int w = rect.right - rect.left;
    int h = rect.bottom - rect.top;

    MoveWindow(g_overlay_hwnd, rect.left, rect.top, w, h, FALSE);
    Py_RETURN_TRUE;
}

/* ─── 设置透明度 ───────────────────────────────────────── */

static PyObject* py_set_opacity(PyObject* self, PyObject* args) {
    float alpha;
    if (!PyArg_ParseTuple(args, "f", &alpha))
        return NULL;

    if (g_overlay_hwnd) {
        int a = (int)(alpha * 255);
        if (a < 0) a = 0;
        if (a > 255) a = 255;
        SetLayeredWindowAttributes(g_overlay_hwnd, 0, (BYTE)a, LWA_ALPHA);
    }
    Py_RETURN_NONE;
}

/* ─── 启用/禁用点击穿透 ──────────────────────────────── */

static PyObject* py_set_click_through(PyObject* self, PyObject* args) {
    int enabled;
    if (!PyArg_ParseTuple(args, "i", &enabled))
        return NULL;

    if (g_overlay_hwnd) {
        LONG ex_style = GetWindowLongW(g_overlay_hwnd, GWL_EXSTYLE);
        if (enabled)
            ex_style |= WS_EX_TRANSPARENT;
        else
            ex_style &= ~WS_EX_TRANSPARENT;
        SetWindowLongW(g_overlay_hwnd, GWL_EXSTYLE, ex_style);
    }
    Py_RETURN_NONE;
}

/* ─── 清空像素缓冲区 ─────────────────────────────────── */

static PyObject* py_clear_pixels(PyObject* self, PyObject* args) {
    if (g_pixels && g_width > 0 && g_height > 0) {
        memset(g_pixels, 0, g_width * g_height * 4);
    }
    Py_RETURN_NONE;
}

/* ─── 提交帧 ─────────────────────────────────────────── */

static PyObject* py_present_frame(PyObject* self, PyObject* args) {
    if (!g_overlay_hwnd || !g_hdc_mem)
        Py_RETURN_NONE;

    BLENDFUNCTION blend = {0};
    blend.BlendOp = AC_SRC_OVER;
    blend.SourceConstantAlpha = 255;
    blend.AlphaFormat = AC_SRC_ALPHA;

    SIZE size = {g_width, g_height};
    POINT src_pos = {0, 0};

    HDC hdc_screen = GetDC(NULL);
    UpdateLayeredWindow(
        g_overlay_hwnd, hdc_screen,
        NULL, &size,
        g_hdc_mem, &src_pos,
        0, &blend, ULW_ALPHA
    );
    ReleaseDC(NULL, hdc_screen);

    Py_RETURN_NONE;
}

/* ─── 绘制填充矩形（ARGB） ───────────────────────────── */

static PyObject* py_draw_rect(PyObject* self, PyObject* args) {
    int x, y, w, h;
    int r, g, b, a;
    if (!PyArg_ParseTuple(args, "iiiiiiii", &x, &y, &w, &h, &r, &g, &b, &a))
        return NULL;

    if (!g_pixels) Py_RETURN_NONE;

    /* 裁剪 */
    int x0 = x < 0 ? 0 : x;
    int y0 = y < 0 ? 0 : y;
    int x1 = (x + w) > g_width ? g_width : (x + w);
    int y1 = (y + h) > g_height ? g_height : (y + h);

    unsigned char *px = (unsigned char *)g_pixels;
    int stride = g_width * 4;

    for (int py = y0; py < y1; py++) {
        unsigned char *row = px + py * stride;
        for (int pxx = x0; pxx < x1; pxx++) {
            int offset = pxx * 4;
            /* BGRA 格式 */
            float sa = a / 255.0f;
            float da = row[offset + 3] / 255.0f;
            float out_a = sa + da * (1.0f - sa);

            if (out_a > 0.001f) {
                row[offset]     = (unsigned char)((b * sa + row[offset] * da * (1.0f - sa)) / out_a);
                row[offset + 1] = (unsigned char)((g * sa + row[offset + 1] * da * (1.0f - sa)) / out_a);
                row[offset + 2] = (unsigned char)((r * sa + row[offset + 2] * da * (1.0f - sa)) / out_a);
            }
            row[offset + 3] = (unsigned char)(out_a * 255);
        }
    }

    Py_RETURN_NONE;
}

/* ─── 获取窗口句柄 ────────────────────────────────────── */

static PyObject* py_get_hwnd(PyObject* self, PyObject* args) {
    return PyLong_FromVoidPtr(g_overlay_hwnd);
}

/* ─── 检查游戏是否运行 ────────────────────────────────── */

static PyObject* py_is_game_running(PyObject* self, PyObject* args) {
    HWND hwnd = FindWindowW(L"D3 Main Window Class", NULL);
    if (hwnd)
        Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}

/* ─── 方法表 ─────────────────────────────────────────── */

static PyMethodDef methods[] = {
    {"create_overlay",      py_create_overlay,      METH_VARARGS, "Create transparent overlay window"},
    {"destroy_overlay",     py_destroy_overlay,     METH_NOARGS,  "Destroy overlay window"},
    {"show",                py_show,                METH_NOARGS,  "Show overlay"},
    {"hide",                py_hide,                METH_NOARGS,  "Hide overlay"},
    {"sync_to_game",        py_sync_to_game,        METH_NOARGS,  "Sync overlay to game window position"},
    {"set_opacity",         py_set_opacity,         METH_VARARGS, "Set overlay opacity (0.0-1.0)"},
    {"set_click_through",   py_set_click_through,   METH_VARARGS, "Enable/disable click-through"},
    {"clear_pixels",        py_clear_pixels,        METH_NOARGS,  "Clear pixel buffer"},
    {"present_frame",       py_present_frame,       METH_NOARGS,  "Push frame to overlay window"},
    {"draw_rect",           py_draw_rect,           METH_VARARGS, "Draw filled rectangle (x,y,w,h,r,g,b,a)"},
    {"get_hwnd",            py_get_hwnd,            METH_NOARGS,  "Get overlay window handle"},
    {"is_game_running",     py_is_game_running,     METH_NOARGS,  "Check if Diablo 3 is running"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT,
    "overlay_core",
    "D3OA transparent overlay core (C extension)",
    -1,
    methods
};

PyMODINIT_FUNC PyInit_overlay_core(void) {
    return PyModule_Create(&module_def);
}
