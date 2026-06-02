# Games Bot — 自动点击工具

为 **Panoptyca** 游戏设计的桌面自动化点击工具。基于 OpenCV 模板匹配识别游戏按钮，按用户配置的顺序循环点击。

## 快速启动

双击 `启动游戏工具.bat`，或命令行：

```bash
cd C:\Users\User\Desktop\Games Bot
python main.py
```

首次使用先装依赖：

```bash
pip install -r requirements.txt
```

## 整体架构

```
Games Bot/
├── main.py                 # 入口：启动 UI + 引擎
├── settings.json           # 持久化配置（自动读写）
├── requirements.txt        # Python 依赖
├── 启动游戏工具.bat         # 双击启动脚本
├── config/
│   └── manager.py          # ConfigManager — JSON 配置读写
├── engine/
│   ├── matcher.py          # match_template — OpenCV 模板匹配
│   └── clicker.py          # ClickEngine — 核心点击循环
├── ui/
│   ├── styles.py           # Qt 样式表
│   ├── floating_window.py  # 悬浮窗口 UI
│   └── calibrator.py       # 截图校准叠加层
└── templates/              # 模板图片（.png）
    ├── button_1.png
    ├── button_2.png
    ├── button_3.png
    ├── button_4.png
    └── button_5.png
```

### 模块职责

| 模块 | 类 / 函数 | 职责 |
|------|-----------|------|
| `config/manager.py` | `ConfigManager` | 读写 `settings.json`，提供属性接口（actions / threshold / round_interval / window_pos 等），每次修改自动 save |
| `engine/matcher.py` | `match_template()` | 单帧截图 + 模板匹配：缩放后归一化相关性匹配，返回最佳匹配坐标 |
| `engine/clicker.py` | `ClickEngine` | 后台线程循环：按 actions 顺序逐个截图→匹配→点击，每个按钮独立超时，支持窗口激活 |
| `ui/floating_window.py` | `FloatingWindow` | 无边框悬浮窗（置顶），可展开/收起，配置按钮列表、阈值、轮次间隔 |
| `ui/calibrator.py` | `CalibratorOverlay` | 全屏半透明覆盖层，拖拽选区截图保存为模板 |
| `ui/styles.py` | 常量 | 暗色主题 Qt 样式表 |

## 核心行为

### 点击循环（ClickEngine._loop）

```
每轮开始 → 重置连续未找到计数
  └─ 按 actions[] 顺序处理每个按钮：
       持续截图 + 模板匹配，直到：
         ✓ 找到 → 点击 → 等待 post_delay 秒
         ✗ 超时（默认 10 秒）→ 跳过，日志记录
         若连续 20 次未找到 → 自动激活游戏窗口
  └─ 一轮完成 → 等待 round_interval 秒 → 下一轮
```

- 全部在 **后台 daemon 线程**运行，不阻塞 UI
- 每帧截图后用 `baseline_resolution` 做缩放适配不同屏幕
- 任意异常会打印到控制台并停止循环

### 连续未找到 → 激活窗口

当截图匹配连续 20 次失败（约 1 秒），ClickEngine 自动调用 `_activate_window()`：
- 用 `win32gui.FindWindow` 按窗口标题 "panoptyca" 查找
- 找到后 `ShowWindow(SW_RESTORE) + SetForegroundWindow` 把游戏窗口切到前台
- 窗口标题硬编码为 `self._window_title = "panoptyca"`，如需改为其他游戏需改此行

## 配置说明（settings.json）

```json
{
  "threshold": 0.8,            // 模板匹配阈值 0.0~1.0
  "baseline_width": 1080,       // 校准时的基准分辨率宽
  "baseline_height": 1920,      // 校准时的基准分辨率高
  "actions": [                  // 点击顺序列表
    {
      "name": "button_1",
      "template": "C:\\path\\to\\button_1.png",
      "post_delay": 2.0,        // 点击后等待秒数
      "timeout": 10             // 超时秒数（找不到就跳过）
    }
  ],
  "round_interval": 10,         // 每轮之间的等待秒数
  "window_geometry": {
    "x": 100, "y": 100,
    "collapsed": false          // UI 是否收起
  }
}
```

所有配置在 UI 上修改后自动写入 JSON。

## 模板截图流程

1. 点击 `📷` 或 `+ 截取模板添加`
2. 全屏覆盖层出现，鼠标拖拽框选按钮区域
3. 松开鼠标 → 裁剪保存到 `templates/` 目录
4. 自动添加到 actions 列表末尾
5. 同时基准分辨率（baseline_width/height）更新为当前屏幕尺寸

## UI 功能

- **拖拽排序**：动作列表支持拖拽调整顺序
- **收起/展开**：运行时只显示状态栏，配置面板可收起
- **状态显示**：当前轮次 / 当前按钮名 / 进度（N/M）/ 倒计时
- **悬浮拖动**：鼠标拖拽窗口任意位置移动

## 故障排查

| 现象 | 可能原因 | 处理方式 |
|------|---------|---------|
| 启动报错 `No module named 'cv2'` | 缺依赖 | `pip install -r requirements.txt` |
| 一直显示"未找到" | 阈值太高 / 按钮截图不匹配 | 降低 threshold（如 0.6）或重新截图 |
| 点了运行没反应 | 没有动作列表 | 先截取至少一个模板按钮 |
| 找不到游戏窗口 | 窗口标题不是 "panoptyca" | 修改 clicker.py 中 `self._window_title` |
| 进度条不刷新 / UI 卡住 | 截图被阻塞 | 检查游戏是否在前台，pyautogui 需要能看到画面 |
