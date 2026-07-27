# D3OA 技术文档

## 1. 架构设计总览

### 1.1 整体架构

```
┌─────────────────────────────────────────────────┐
│                  D3OA 主进程                      │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ GameMon  │  │  Config   │  │  PluginMgr    │  │
│  │ 游戏监控  │  │  配置管理  │  │  插件管理器    │  │
│  └────┬─────┘  └────┬─────┘  └──────┬────────┘  │
│       │              │               │            │
│  ┌────▼──────────────▼───────────────▼────────┐  │
│  │            Overlay Manager                  │  │
│  │         透明叠加窗口管理器                    │  │
│  │  ┌─────────────────────────────────────┐   │  │
│  │  │  Renderer (Pygame/PyQt 渲染层)       │   │  │
│  │  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐  │   │  │
│  │  │  │计时器│ │构筑表│ │进度条│ │热键  │  │   │  │
│  │  │  └─────┘ └─────┘ └─────┘ └─────┘  │   │  │
│  │  └─────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────┘  │
│                      │                            │
│  ┌───────────────────▼────────────────────────┐  │
│  │        C Extension (overlay_core)           │  │
│  │  Win32 API · 透明窗口 · 截图捕获 · 像素处理   │  │
│  └─────────────────────────────────────────────┘  │
│                      │                            │
└──────────────────────┼────────────────────────────┘
                       │
              Win32 Desktop (游戏窗口上方)
```

### 1.2 数据流

```
                    ┌─────────────┐
                    │ Diablo 3    │
                    │ 游戏窗口     │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐   ┌─────▼─────┐   ┌──────▼─────┐
    │ API 数据   │   │ 日志文件   │   │  截图 OCR   │
    │ (角色/构筑)│   │ (实时事件) │   │ (界面信息)  │
    └─────┬─────┘   └─────┬─────┘   └──────┬─────┘
          │               │                 │
          └───────────────┼─────────────────┘
                          │
                    ┌─────▼─────┐
                    │ DataProvider│
                    │  数据聚合层  │
                    └─────┬─────┘
                          │
                    ┌─────▼─────┐
                    │  插件消费   │
                    │  数据处理   │
                    └─────┬─────┘
                          │
                    ┌─────▼─────┐
                    │  Overlay   │
                    │  渲染输出   │
                    └───────────┘
```

## 2. 核心技术：透明叠加窗口

### 2.1 Win32 透明窗口原理

Windows 提供了 **分层窗口 (Layered Window)** 机制，允许创建透明/半透明窗口：

```c
// 关键 Win32 API 调用链

// 1. 创建窗口时添加 WS_EX_LAYERED 扩展样式
HWND hwnd = CreateWindowEx(
    WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
    "D3OverlayClass", "D3OA",
    WS_POPUP,
    x, y, width, height,
    NULL, NULL, hInstance, NULL
);

// 2. 设置窗口为完全不透明度 + 颜色键透明
SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA);

// 3. 启用点击穿透 — WS_EX_TRANSPARENT
// 鼠标事件将穿透此窗口传递给下方的游戏窗口
LONG exStyle = GetWindowLong(hwnd, GWL_EXSTYLE);
SetWindowLong(hwnd, GWL_EXSTYLE, exStyle | WS_EX_TRANSPARENT);

// 4. 使用 UpdateLayeredWindow 实现像素级控制
// 可以指定每个像素的 alpha 值
BLENDFUNCTION blend = {0};
blend.BlendOp = AC_SRC_OVER;
blend.SourceConstantAlpha = 255;
blend.AlphaFormat = AC_SRC_ALPHA;  // 使用源 alpha 通道
UpdateLayeredWindow(hwnd, hdcDst, &wndPos, &size, hdcSrc, &srcPos, 0, &blend, ULW_ALPHA);
```

### 2.2 安全性保证

| 行为 | D3OA | 典型外挂 | 说明 |
|------|------|----------|------|
| 读取游戏内存 | ❌ 不读 | ✅ 读取 | 我们不触及游戏进程地址空间 |
| 注入 DLL | ❌ 不注入 | ✅ 注入 | 不创建远程线程 |
| Hook API | ❌ 不 Hook | ✅ Hook | 不拦截任何 Win32/DirectX 调用 |
| 修改游戏文件 | ❌ 不修改 | ✅ 修改 | 只读取公开 API 和日志 |
| 窗口叠加 | ✅ 独立窗口 | — | 使用标准 Windows 窗口机制 |
| 鼠标穿透 | ✅ WS_EX_TRANSPARENT | — | 标准 Win32 扩展样式 |

**结论**：D3OA 对游戏进程完全"只读"，使用的是操作系统级别的标准窗口管理，
与 OBS 录屏、Discord Overlay 等合法工具使用相同的技术原理。

### 2.3 窗口同步

叠加窗口需要跟随游戏窗口移动/缩放：

```python
def sync_overlay_position(self):
    """将叠加窗口同步到游戏窗口的位置和大小"""
    game_hwnd = win32gui.FindWindow("D3 Main Window Class", None)
    if not game_hwnd:
        return False

    rect = win32gui.GetWindowRect(game_hwnd)
    x, y, right, bottom = rect
    w, h = right - x, bottom - y

    # 移动叠加窗口到游戏窗口上方
    win32gui.MoveWindow(self.hwnd, x, y, w, h, False)
    return True
```

## 3. 数据源详解

### 3.1 Blizzard D3 公开 API

Blizzard 提供 Diablo 3 Web API，但**强制需要 OAuth2 access_token**：
通过 client-credentials 流程换取
（`POST https://{region}.battle.net/oauth/token`，`grant_type=client_credentials`，
Basic Auth 用 Client ID:Secret）。端点返回 403 时无有效 token。

```text
获取 token: POST https://{region}.battle.net/oauth/token
查询接口:   GET  https://{region}.api.blizzard.com/d3/...?access_token=TOKEN
```

> 注意：早期文档称"无需认证即可查询公开角色信息"，**不实**。D3OA 已在
> `D3APIClient._ensure_token()` 中实现自动换取；用户需在 config.json 填入
> `client_id` / `client_secret`（或从 develop.battle.net 申请），或手动填 `access_token`。
端点列表:
GET /profile/{battleTag}/              # 玩家档案（生涯数据）
GET /profile/{battleTag}/hero/{heroId} # 英雄详细信息
GET /profile/{battleTag}/hero/{heroId}/items # 英雄装备
GET /era/{eraId}/leaderboard/rift-team-2 # 天梯排行榜
GET /data/item/{itemSlug}              # 物品数据
GET /data/artisan/{artisanSlug}        # 工匠数据
GET /data/follower/{followerSlug}      # 追随者数据
```

**Python 实现**：

```python
import requests

class D3API:
    BASE_URL = "https://{region}.api.blizzard.com/d3"

    def __init__(self, api_key, region="us"):
        self.api_key = api_key
        self.region = region
        self.base = self.BASE_URL.format(region=region)

    def get_profile(self, battle_tag):
        """获取玩家档案"""
        tag = battle_tag.replace("#", "-")
        url = f"{self.base}/profile/{tag}/"
        return self._request(url)

    def get_hero(self, battle_tag, hero_id):
        """获取英雄详情（含装备、技能）"""
        tag = battle_tag.replace("#", "-")
        url = f"{self.base}/profile/{tag}/hero/{hero_id}"
        return self._request(url)

    def _request(self, url):
        resp = requests.get(url, params={"access_token": self.api_key})
        resp.raise_for_status()
        return resp.json()
```

### 3.2 游戏日志文件

Diablo 3 在游戏目录下生成日志文件，包含游戏事件：

```
路径示例:
%USERPROFILE%/Documents/Diablo III/Logs/D3Debug.txt

可解析事件:
- 传送点使用
- 组队信息
- 游戏难度/模式切换
- 物品掉落（部分）
```

```python
import os
import time

class LogWatcher:
    """监控 D3 日志文件变化，提取游戏事件"""

    def __init__(self, log_path=None):
        self.log_path = log_path or self._find_log()
        self._last_pos = 0

    def _find_log(self):
        """自动定位 D3 日志文件"""
        base = os.path.expanduser("~/Documents/Diablo III/Logs")
        log_file = os.path.join(base, "D3Debug.txt")
        return log_file if os.path.exists(log_file) else None

    def poll_new_lines(self):
        """读取新增的日志行"""
        if not self.log_path or not os.path.exists(self.log_path):
            return []

        with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(self._last_pos)
            lines = f.readlines()
            self._last_pos = f.tell()

        return [l.strip() for l in lines if l.strip()]

    def parse_events(self, lines):
        """从日志行中提取结构化事件"""
        events = []
        for line in lines:
            if "Game_NewGame" in line:
                events.append({"type": "new_game", "raw": line})
            elif "Game_Leave" in line:
                events.append({"type": "leave_game", "raw": line})
            elif "NephalemRift" in line:
                events.append({"type": "rift_event", "raw": line})
        return events
```

### 3.3 截图 OCR（可选高级功能）

使用 `win32gui` 捕获游戏窗口截图，通过 OCR 提取界面文字：

```python
import win32gui
import win32ui
import win32con
from PIL import Image

def capture_game_window(hwnd=None):
    """截取游戏窗口画面（只读操作，不修改游戏）"""
    if hwnd is None:
        hwnd = win32gui.FindWindow("D3 Main Window Class", None)
    if not hwnd:
        return None

    rect = win32gui.GetWindowRect(hwnd)
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]

    # 创建设备上下文
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()

    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bitmap)

    # 捕获窗口内容（不修改游戏）
    result = save_dc.BitBlt((0, 0), (w, h), mfc_dc, (0, 0), win32con.SRCCOPY)

    # 转换为 PIL Image
    bmp_info = bitmap.GetInfo()
    bmp_str = bitmap.GetBitmapBits(True)
    img = Image.frombuffer(
        'RGB',
        (bmp_info['bmWidth'], bmp_info['bmHeight']),
        bmp_str, 'raw', 'BGRX', 0, 1
    )

    # 清理
    win32gui.DeleteObject(bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    return img
```

## 4. 插件系统

### 4.1 插件接口

```python
from abc import ABC, abstractmethod

class PluginBase(ABC):
    """插件基类 — 所有插件必须继承此类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本"""
        ...

    @property
    def description(self) -> str:
        """插件描述"""
        return ""

    @abstractmethod
    def on_init(self, context: dict):
        """初始化回调，context 包含 overlay、config、api 等"""
        ...

    @abstractmethod
    def on_update(self, delta_time: float, game_data: dict):
        """每帧更新回调"""
        ...

    @abstractmethod
    def on_render(self, surface):
        """渲染回调，在叠加层上绘制内容"""
        ...

    def on_destroy(self):
        """清理回调"""
        pass

    def on_config_changed(self, config: dict):
        """配置变更回调"""
        pass
```

### 4.2 插件注册与加载

```python
import importlib
import os

class PluginManager:
    def __init__(self, plugin_dir="plugins"):
        self.plugin_dir = plugin_dir
        self.plugins: dict[str, PluginBase] = {}

    def discover_and_load(self, context: dict):
        """自动发现并加载所有插件"""
        plugin_dir = os.path.join(os.path.dirname(__file__), self.plugin_dir)
        for fname in os.listdir(plugin_dir):
            if fname.endswith('.py') and not fname.startswith('_'):
                module_name = fname[:-3]
                try:
                    module = importlib.import_module(
                        f".{self.plugin_dir}.{module_name}", package="d3_overlay"
                    )
                    if hasattr(module, 'Plugin'):
                        plugin = module.Plugin()
                        plugin.on_init(context)
                        self.plugins[plugin.name] = plugin
                except Exception as e:
                    print(f"Failed to load plugin {module_name}: {e}")

    def update_all(self, delta_time, game_data):
        for p in self.plugins.values():
            p.on_update(delta_time, game_data)

    def render_all(self, surface):
        for p in self.plugins.values():
            p.on_render(surface)
```

## 5. 配置系统

### 5.1 配置文件格式 (`config/default.json`)

```json
{
  "overlay": {
    "opacity": 0.85,
    "position": "top-right",
    "font_size": 14,
    "theme": "dark",
    "click_through": true,
    "follow_game_window": true
  },
  "hotkeys": {
    "toggle_overlay": "F8",
    "toggle_timer": "F9",
    "cycle_layout": "F10",
    "settings": "F11"
  },
  "data": {
    "battle_tag": "",
    "region": "us",
    "log_path": "auto",
    "api_cache_ttl": 300,
    "ocr_enabled": false
  },
  "plugins": {
    "timer": { "enabled": true, "position": [20, 20] },
    "build_info": { "enabled": true, "position": [20, 120] },
    "nemesis": { "enabled": true, "position": [20, 300] },
    "rift_info": { "enabled": true, "position": [20, 400] }
  }
}
```

## 6. 渲染系统

### 6.1 渲染流程

```
每帧:
1. 检测游戏窗口位置 → 同步叠加窗口
2. 清空渲染缓冲区
3. 遍历启用的插件 → 各插件渲染到缓冲区
4. 将缓冲区通过 UpdateLayeredWindow 推送到叠加窗口
5. 等待下一帧（目标 30fps，低 CPU 占用）
```

### 6.2 字体与文字渲染

使用 Pygame 或 PIL 进行文字渲染，输出 ARGB 位图传给 Win32 叠加层：

```python
import pygame

class TextRenderer:
    def __init__(self, font_name="Microsoft YaHei", font_size=14):
        pygame.font.init()
        self.font = pygame.font.SysFont(font_name, font_size)

    def render_text(self, text, color=(255, 255, 255), bg=None):
        """渲染文字为带 Alpha 通道的 Surface"""
        surface = self.font.render(text, True, color, bg)
        return surface
```

## 7. 扩展路线图

### Phase 1 — 基础框架 (MVP)
- [x] 透明叠加窗口创建
- [x] 游戏窗口检测与跟随
- [x] 基础渲染引擎
- [x] 配置系统

### Phase 2 — 核心插件
- [ ] 秘境计时器
- [ ] 构筑信息展示（API 数据）
- [ ] 热键管理系统

### Phase 3 — 高级功能
- [ ] 截图 OCR 识别
- [ ] 语音播报
- [ ] 数据统计与图表
- [ ] 多语言支持

### Phase 4 — 社区生态
- [ ] 插件市场
- [ ] 用户自定义主题
- [ ] 云端配置同步
- [ ] 团队协作模式

## 8. API 参考

### 8.1 OverlayManager

```python
class OverlayManager:
    """叠加窗口管理器"""

    def __init__(self, config: dict): ...
    def create_overlay(self) -> bool: ...
    def destroy(self): ...
    def set_opacity(self, alpha: float): ...
    def set_click_through(self, enabled: bool): ...
    def sync_to_game_window(self) -> bool: ...
    def update_surface(self, pixels: bytes, width: int, height: int): ...
    def toggle_visibility(self): ...
```

### 8.2 GameMonitor

```python
class GameMonitor:
    """游戏进程监控"""

    def __init__(self, process_name: str = "Diablo III64.exe"): ...
    def is_game_running(self) -> bool: ...
    def get_game_hwnd(self) -> int: ...
    def get_window_rect(self) -> tuple: ...
    def is_foreground(self) -> bool: ...
    def on_game_state_changed(self, callback: Callable): ...
```

### 8.3 DataProvider

```python
class DataProvider:
    """数据聚合提供器"""

    def __init__(self, config: dict): ...
    def get_hero_data(self, battle_tag: str, hero_id: int) -> dict: ...
    def get_rift_progress(self) -> dict: ...
    def get_log_events(self) -> list: ...
    def get_cached(self, key: str) -> Any: ...
    def set_cache(self, key: str, value: Any, ttl: int): ...
```

## 9. 编译与部署

### 9.1 C 扩展编译

```python
# setup.py
from setuptools import setup, Extension

overlay_core = Extension(
    'overlay_core',
    sources=['src/overlay_core.c'],
    libraries=['user32', 'gdi32', 'dwmapi'],
)

setup(
    name='d3-overlay',
    ext_modules=[overlay_core],
)
```

### 9.2 打包为 EXE

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=assets/icon.ico src/main.py
```

## 10. 常见问题

**Q: 会被封号吗？**
A: 不会。D3OA 不读取/修改游戏内存，不注入 DLL，不修改游戏文件。
它使用的是操作系统级别的标准透明窗口，与 OBS、Discord Overlay 技术一致。
暴雪的 Warden 反作弊系统只检测进程注入和内存修改。

**Q: 为什么不用 C# 或 Electron？**
A: Python + C 的组合兼顾了开发效率和性能。Python 处理逻辑和 API 调用，
C 处理 Win32 API 调用和像素操作。未来如需更优性能可考虑 Rust。

**Q: 支持全屏模式吗？**
A: 支持窗口化和无边框窗口化模式。独占全屏模式下叠加窗口不可见（Windows 系统限制）。
推荐使用"无边框窗口化"模式以获得最佳效果。
